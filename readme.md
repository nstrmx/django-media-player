# Django Media Player
Simple django media player implementation with shared web worker for learging purposes. 
## Add media
```
python manage.py add_media --audio-dir ~/Music --video-dir ~/Videos/ --skip-existing-paths
```
Launches N workers to calculate md5 hex in parallel while adding new media to database, where N is number of CPUs on your machine.
## Screenshots
### Audio / Radio
![alt text](images/image.png)
![alt text](images/image-4.png)
### Video
![alt text](images/image-1.png)
![alt text](images/image-5.png)