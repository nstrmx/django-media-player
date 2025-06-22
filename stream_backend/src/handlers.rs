use actix_files::NamedFile;
use actix_web::{
    body::BoxBody, 
    http::header::{
        ACCEPT_RANGES,
        CONTENT_LENGTH,
        CONTENT_RANGE,
        HeaderValue,
    }, 
    HttpRequest, 
    HttpResponse, 
    Responder, 
    Result
};
use bytes::Bytes;
use futures::Stream;
use rustls_pki_types::ServerName;
use std::{
    io::{self, Seek, SeekFrom},
    path::PathBuf,
    str,
    sync::Arc,
    pin::Pin
};
use tokio::{
    io::{
        AsyncRead, AsyncWrite, AsyncReadExt, AsyncBufReadExt, AsyncWriteExt, 
        BufReader
    },
    net::TcpStream,
};
use tokio_rustls::{TlsConnector, rustls::{ClientConfig, RootCertStore}};
use url::Url;
use webpki_roots::TLS_SERVER_ROOTS;


trait AsyncReadWrite: AsyncRead + AsyncWrite {}
impl<T: AsyncRead + AsyncWrite> AsyncReadWrite for T {}


pub struct FileStream {
    file: NamedFile,
}

impl FileStream {
    pub async  fn new(file_path: PathBuf) -> Result<Self> {
        let file = actix_files::NamedFile::open_async(file_path).await?;
        Ok(Self {file})
    }
}

impl Responder for FileStream {
    type Body = BoxBody;

    fn respond_to(mut self, req: &HttpRequest) -> HttpResponse<Self::Body> {
        let file_size = self.file.metadata().len();
        let start: u64 = req.headers().get("Range").unwrap() 
            .to_str().unwrap()
            .split("=").collect::<Vec<&str>>()[1] 
            .split("-").collect::<Vec<&str>>()[0].parse().unwrap();
        let end = file_size;
        let _pos = self.file.seek(SeekFrom::Start(start)).unwrap();
        let mut response = self.file.into_response(req);
        let headers = response.headers_mut();
        headers.insert(
            ACCEPT_RANGES,
            HeaderValue::from_static("bytes")
        );
        headers.insert(
            CONTENT_LENGTH,
            HeaderValue::from_str(&format!("{}", end - start)).unwrap()
        );
        headers.insert(
            CONTENT_RANGE,
            HeaderValue::from_str(&format!(
                "bytes {}-{}/{}", start, end - 1, file_size
            )).unwrap()
        );
        response
    }
}


pub struct HttpStream {
    stream: Pin<Box<dyn Stream<Item = Result<Bytes, io::Error>> + 'static>>,
}

impl HttpStream {
    pub async fn new(url: &str, chunk_size: usize) -> Result<Self> {
        let mut input_stream = Self::stream_url(url).await?;
        let output_stream = async_stream::stream! {
            let mut buffer = vec![0; chunk_size];
            while let Some(chunk) = match input_stream.read(&mut buffer).await {
                Ok(0) => None, // End of stream
                Ok(n) => Some(Ok(Bytes::from(buffer[..n].to_owned()))),
                Err(e) => Some(Err(e)),
            } {
                yield chunk;
            }
        };
        Ok(Self{stream: Box::pin(output_stream)})
    }

    async fn stream_url(url: &str) -> Result<Box<dyn AsyncReadWrite + Unpin + Send>> {
        let parsed_url = Url::parse(url).expect("Invalid URL");
        let host = parsed_url.host_str().unwrap().to_string();
        let path = parsed_url.path().to_string();
        let mut tcp_stream: Box<dyn AsyncReadWrite + Unpin + Send> = match parsed_url.scheme() {
            "http" => {
                let port = parsed_url.port().unwrap_or(80);
                let addr = format!("{}:{}", host, port);
                let tcp_stream = TcpStream::connect(addr).await?;
                Box::new(tcp_stream)
            },
            "https" => {
                let port = parsed_url.port().unwrap_or(443);
                let addr = format!("{}:{}", host, port);
                let tcp_stream = TcpStream::connect(addr).await?;
                let mut root_cert_store = RootCertStore::empty();
                root_cert_store.extend(TLS_SERVER_ROOTS.iter().cloned());
                let tls_config = ClientConfig::builder()
                    .with_root_certificates(root_cert_store)
                    .with_no_client_auth();
                let tls_connector = TlsConnector::from(Arc::new(tls_config));
                let dns_name = ServerName::try_from(host.to_owned()).map_err(
                    |_| io::Error::new(
                        io::ErrorKind::InvalidInput, 
                        "Invalid hostname"
                    )
                )?;
                let tls_stream = tls_connector.connect(dns_name, tcp_stream).await?;
                Box::new(tls_stream)
            },
            _ => return Err(actix_web::error::ErrorBadRequest("Unsupported scheme")),
        };
        tcp_stream.write_all(format!("GET {} HTTP/1.0\r\n", path).as_bytes()).await?;
        tcp_stream.write_all(format!("Host: {}\r\n", host).as_bytes()).await?;
        tcp_stream.write_all(b"User-Agent: Rust-Stream\r\n").await?;
        tcp_stream.write_all(b"Connection: close\r\n\r\n").await?;
        tcp_stream.flush().await?;
        let mut reader = BufReader::new(tcp_stream);
        let mut line = String::new();
        loop {
            line.clear();
            let bytes_read = reader.read_line(&mut line).await?;
            if bytes_read == 0 || line.trim().is_empty() {
                // TODO skip headers for now
                // Some radio streams return ICY 200 OK which can't be interpreted by
                // typical http request libraries
                break;
            }
        }
        Ok(reader.into_inner())
    }
}

impl Responder for HttpStream {
    type Body = BoxBody;

    fn respond_to(self, _req: &HttpRequest) -> HttpResponse<Self::Body> {
        HttpResponse::Ok().streaming(self.stream)
    }
}
