class VideoPlayer extends MediaPlayer {
    constructor(){
        super();
    }
    get_type() {
        return "video";
    }
    get_controller_type(){
        return "video";
    }
}
