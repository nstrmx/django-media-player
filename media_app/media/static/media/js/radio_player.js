class RadioPlayer extends MediaPlayer {
    constructor() {
        super();
    }
    get_type() {
        return "radio";
    }
    get_controller_type(){
        return "audio";
    }
    request_update_duration(duration){
        return;
    }
}