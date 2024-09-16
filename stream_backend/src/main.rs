use actix_web::{
    get, web, App, HttpRequest, HttpResponse, HttpServer, Responder, Result
};
use serde::Deserialize;
use sqlx::sqlite::SqlitePool;
use std::{
    path::PathBuf,
    str,
};
mod handlers;


#[derive(Deserialize)]
struct MediaQuery {
    id: usize,
    media_type: String,
}


#[get("/media")]
async fn media_view(
    request: HttpRequest,
    query: web::Query<MediaQuery>,
    db_pool: web::Data<SqlitePool>,
) -> Result<HttpResponse> {
    let media_type = match query.media_type.as_str() {
        "audio" => "audio",
        "video" => "video",
        "radio" => "radio",
        _ => return Err(actix_web::error::ErrorBadRequest("Invalid media type")),
    };
    let query_str = format!("SELECT path FROM media_{} WHERE id = ?", media_type);
    let row: (String,) = sqlx::query_as(&query_str)
        .bind(query.id as i64)
        .fetch_one(db_pool.get_ref())
        .await
        .map_err(|_| actix_web::error::ErrorNotFound("Media not found"))?;
    let path = row.0;
    match query.media_type.as_str() {
        "audio" | "video" => {
            let file_path = PathBuf::from(&path);
            let file_stream = handlers::FileStream::new(file_path).await?;
            Ok(file_stream.respond_to(&request))
        }
        "radio" => {
            let http_stream = handlers::HttpStream::new(&path, 4096).await?;
            Ok(http_stream.respond_to(&request))
        }
        _ => Err(actix_web::error::ErrorBadRequest("Unsupported media type")),
    }
}


#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let db_pool = SqlitePool::connect("sqlite:../db.sqlite3").await
        .expect("Failed to connect to the database");
    HttpServer::new(move || {
        App::new()
            .app_data(web::Data::new(db_pool.to_owned()))
            .service(media_view)
    })
    .bind("127.0.0.1:8080")?
    .run()
    .await
}
