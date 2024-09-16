class MediaPlayer {
    constructor({worker, media_type, playlist}) {
        this.worker = worker;
        this.media_type = media_type;
        this.repeat_mode_list = ["one", "page", "all"];
        this.state = {
            id: null,
            repeat_idx: 1,
            playlist: playlist,
        };
        this.mount();
        this.controller.volume = window.localStorage.getItem("player_vol") / 100;
        const repeat_name = this.repeat_mode_list[this.state.repeat_idx];
        this.$repeat.text(`repeat: ${repeat_name}`);
        this.add_event_listeners()
    }

    get controller_type(){
        if (this.media_type === "audio" || this.media_type === "radio") {
            return "audio";
        } else if (this.media_type === "video") {
            return "video";
        } else {
            throw Error("not implemented");
        }
    }

    get controller() {
        return this.$controller[0];
    }

    mount() {
        const ctype = this.controller_type;
        const $player = $(`
<center id="player_container">
    <div>
        <${ctype} controls autoplay preload="metadata" src="" id="media_controller" style="width: 100%;"></${ctype}>
    </div>
    <p style="width: 100%">
        <div style="width: 100%"></div>
        <button id="prev">prev</button>
        <button id="next">next</button>
        <button id="repeat">repeat</button>
        <div style="width: 100%"></div>
    </p>
    <p id="info" style="width: 100%">
    </p>
</center>
        `);
        $("#root").html($player);
        this.$container = $("#player_container").first();
        this.$controller = $("#media_controller").first();
        this.$next = $("#next").first();
        this.$prev = $("#prev").first();
        this.$repeat = $("#repeat").first();
    }

    add_event_listeners() {
        this.$controller.on("play", e => {
            $(window).trigger("player:play", {
                media: {
                    type: this.media_type,
                    id: this.state.id,
                }
            });
        });
        this.$controller.on("pause", e => {
            $(window).trigger("player:pause", {
                media: {
                    type: this.media_type,
                    id: this.state.id,
                }
            });
        });
        this.$controller.on("ended", e => {
            const repeat_name = this.repeat_mode_list[this.state.repeat_idx];
            switch (repeat_name) {
                case "one":
                    this.play(this.state.id);
                    break;
                case "page":
                case "all":
                    this.play_next();
                    break;
                default:
                    throw Error("not implemented");
            }
        });
        this.$controller.on("volumechange", e => {
            const value = Math.round(e.currentTarget.volume * 100);
            window.localStorage.setItem("player_vol", value);
        });
        this.$controller.on("canplay", e => {}); 
        this.$repeat.click(e => {
            e.preventDefault();
            this.state.repeat_idx = (this.state.repeat_idx + 1) % this.repeat_mode_list.length;
            const repeat_name = this.repeat_mode_list[this.state.repeat_idx];
            $("#repeat").text(`repeat: ${repeat_name}`);
        });
        this.$next.click(e => this.play_next());
        this.$prev.click(e => this.play_prev());
    }

    find_current_row() {
        for (let idx in this.state.playlist) {
            if (this.state.id === this.state.playlist[idx].id) {
                return [idx, this.state.playlist[idx]];
            }
        }
    }

    request_update_duration(duration) {
        $.ajax({
            url: global.urls.update_duration,
            type: "POST",
            headers: {'X-CSRFToken': window.get_cookie("csrftoken")},
            dataType: 'json',
            data: {
                id: this.state.id,
                type: this.media_type,
                duration: duration,
            },
            success: r => {
                // const $row = this.find_current_row();
                // const $dur = $row.find(".field-duration").first();
                // $dur.text(format_duration(duration * 1000));
            }
        })
    }

    request_update_play_count() {
        $.ajax({
            url: global.urls.update_play_count,
            type: "POST",
            headers: {'X-CSRFToken': window.get_cookie("csrftoken")},
            dataType: 'json',
            data: {
                id: this.state.id,
                type: this.media_type,
            },
            success: r => {
                // const $row = this.find_current_row();
                // const $pc = $row.find(".field-play_count").first();
                // $pc.text(+($pc.text()) + 1);
            }
        })
    }

    play(id) {
        this.$controller.attr("src", `${global.urls.file_stream}?id=${id}&media_type=${this.media_type}`);
        this.state.id = id;
        const interval = setInterval(() => {
            if (this.controller.paused) {
                this.controller.play();
            } else {
                clearInterval(interval);
            }
        }, 1000);
    }

    pause() {
        this.controller.pause();
    }

    resume() {
        this.controller.play();
        $(window).trigger("player:resume", {
            media_type: this.media_type,
            media_id: this.state.id,
        });
    }

    has_src() {
        return this.$controller.attr("src").length > 0;
    }

    is_paused() {
        return this.controller.paused;
    }

    is_current_id(id) {
        return id == this.state.id;
    }

    play_next() {
        switch (this.state.repeat_idx) {
        case 0:
            return;
        case 1:
            const [idx, row] = this.find_current_row();
            const id = this.state.playlist[
                (+idx + 1) % this.state.playlist.length
            ].id
            this.play(id);
            break;
        case 2:
            return;
        }
    }

    play_prev(){
        switch (this.state.repeat_idx) {
        case 0:
            return;
        case 1:
            const [idx, row] = this.find_current_row();
            const id = this.state.playlist[
                (idx <= 0 ? this.state.playlist.length : idx) - 1
            ].id
            this.play(id);
            break;
        case 2:
            return;
        }
    }
}


