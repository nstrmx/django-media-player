class AudioPlayer extends MediaPlayer {
    constructor() {
        super();
    }
    get_type(){
        return "audio";
    }
    get_controller_type(){
        return "audio";
    }
}