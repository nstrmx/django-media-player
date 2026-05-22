use actix_files::NamedFile;
use actix_web::{
    body::BoxBody,
    http::header::CONTENT_TYPE,
    HttpRequest,
    HttpResponse,
    Responder,
    Result,
};
use bytes::Bytes;
use futures::Stream;
use rustls_pki_types::ServerName;
use std::{
    io,
    path::PathBuf,
    pin::Pin,
    sync::Arc,
};
use tokio::{
    io::{
        AsyncBufReadExt, AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt,
        BufReader,
    },
    net::TcpStream,
    time::{timeout, Duration},
};
use tokio_rustls::{
    rustls::{ClientConfig, RootCertStore},
    TlsConnector,
};
use url::Url;
use webpki_roots::TLS_SERVER_ROOTS;


const CONNECT_TIMEOUT: Duration = Duration::from_secs(15);


trait AsyncReadWrite: AsyncRead + AsyncWrite {}
impl<T: AsyncRead + AsyncWrite> AsyncReadWrite for T {}


pub struct FileStream {
    file: NamedFile,
}

impl FileStream {
    pub async fn new(file_path: PathBuf) -> Result<Self> {
        let file = actix_files::NamedFile::open_async(file_path).await?;
        Ok(Self { file })
    }
}

impl Responder for FileStream {
    type Body = BoxBody;

    fn respond_to(self, req: &HttpRequest) -> HttpResponse<Self::Body> {
        self.file.into_response(req)
    }
}


pub struct HttpStream {
    stream: Pin<Box<dyn Stream<Item = Result<Bytes, io::Error>> + 'static>>,
    content_type: Option<String>,
}

impl HttpStream {
    pub async fn new(url: &str, chunk_size: usize) -> Result<Self> {
        let (buffered, mut input_stream, content_type) = Self::stream_url(url).await?;
        let mut read_buf = vec![0u8; chunk_size];
        let output_stream = async_stream::stream! {
            if !buffered.is_empty() {
                yield Ok(Bytes::from(buffered));
            }
            loop {
                match input_stream.read(&mut read_buf).await {
                    Ok(0) => break,
                    Ok(n) => yield Ok(Bytes::copy_from_slice(&read_buf[..n])),
                    Err(e) => {
                        yield Err(e);
                        return;
                    }
                }
            }
        };
        Ok(Self { stream: Box::pin(output_stream), content_type })
    }

    async fn stream_url(
        url: &str,
    ) -> Result<(Vec<u8>, Box<dyn AsyncReadWrite + Unpin + Send>, Option<String>)> {
        let parsed_url = Url::parse(url)
            .map_err(|_| actix_web::error::ErrorBadRequest("Invalid URL"))?;
        let host = parsed_url
            .host_str()
            .ok_or_else(|| actix_web::error::ErrorBadRequest("URL missing host"))?
            .to_string();
        let path = parsed_url.path().to_string();

        let mut tcp_stream: Box<dyn AsyncReadWrite + Unpin + Send> = match parsed_url.scheme() {
            "http" => {
                let port = parsed_url.port().unwrap_or(80);
                let addr = format!("{}:{}", host, port);
                let stream = timeout(CONNECT_TIMEOUT, TcpStream::connect(&addr))
                    .await
                    .map_err(|_| io::Error::new(io::ErrorKind::TimedOut, "Connection timed out"))?
                    .map_err(|e| io::Error::new(io::ErrorKind::ConnectionRefused, e))?;
                Box::new(stream)
            }
            "https" => {
                let port = parsed_url.port().unwrap_or(443);
                let addr = format!("{}:{}", host, port);
                let raw = timeout(CONNECT_TIMEOUT, TcpStream::connect(&addr))
                    .await
                    .map_err(|_| io::Error::new(io::ErrorKind::TimedOut, "Connection timed out"))?
                    .map_err(|e| io::Error::new(io::ErrorKind::ConnectionRefused, e))?;

                let mut root_cert_store = RootCertStore::empty();
                root_cert_store.extend(TLS_SERVER_ROOTS.iter().cloned());
                let tls_config = ClientConfig::builder()
                    .with_root_certificates(root_cert_store)
                    .with_no_client_auth();
                let tls_connector = TlsConnector::from(Arc::new(tls_config));
                let dns_name = ServerName::try_from(host.clone())
                    .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "Invalid hostname"))?;

                let tls = timeout(CONNECT_TIMEOUT, tls_connector.connect(dns_name, raw))
                    .await
                    .map_err(|_| io::Error::new(io::ErrorKind::TimedOut, "TLS handshake timed out"))?
                    .map_err(|e| io::Error::new(io::ErrorKind::ConnectionAborted, e))?;
                Box::new(tls)
            }
            _ => return Err(actix_web::error::ErrorBadRequest("Unsupported scheme")),
        };

        tcp_stream.write_all(b"GET ").await?;
        tcp_stream.write_all(path.as_bytes()).await?;
        tcp_stream.write_all(b" HTTP/1.0\r\n").await?;
        tcp_stream.write_all(b"Host: ").await?;
        tcp_stream.write_all(host.as_bytes()).await?;
        tcp_stream.write_all(b"\r\n").await?;
        tcp_stream.write_all(b"User-Agent: Rust-Stream\r\n").await?;
        tcp_stream.write_all(b"Connection: close\r\n\r\n").await?;
        tcp_stream.flush().await?;

        let mut reader = BufReader::new(tcp_stream);

        let mut status_line = String::new();
        reader.read_line(&mut status_line).await?;
        let status_line = status_line.trim();
        if !status_line.starts_with("HTTP/") && !status_line.starts_with("ICY") {
            return Err(actix_web::error::ErrorBadRequest(format!(
                "Unexpected response: {}",
                status_line
            )));
        }

        let code: u16 = status_line
            .splitn(3, ' ')
            .nth(1)
            .and_then(|s| s.parse().ok())
            .ok_or_else(|| actix_web::error::ErrorBadRequest("Invalid status line"))?;
        if code < 200 || code >= 300 {
            return Err(actix_web::error::ErrorBadRequest(format!(
                "Upstream returned status {}",
                code
            )));
        }

        let mut content_type = None;
        let mut line = String::new();
        loop {
            line.clear();
            let bytes_read = reader.read_line(&mut line).await?;
            if bytes_read == 0 || line.trim().is_empty() {
                break;
            }
            let lower = line.to_lowercase();
            if content_type.is_none() {
                if let Some(val) = lower.strip_prefix("content-type:") {
                    content_type = Some(val.trim().to_string());
                } else if let Some(val) = lower.strip_prefix("icy-content-type:") {
                    content_type = Some(val.trim().to_string());
                }
            }
        }

        let buffered = reader.buffer().to_vec();
        Ok((buffered, reader.into_inner(), content_type))
    }
}

impl Responder for HttpStream {
    type Body = BoxBody;

    fn respond_to(self, _req: &HttpRequest) -> HttpResponse<Self::Body> {
        let mut resp = HttpResponse::Ok();
        if let Some(ct) = &self.content_type {
            resp.insert_header((CONTENT_TYPE, ct.as_str()));
        }
        resp.streaming(self.stream)
    }
}
