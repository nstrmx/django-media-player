class MediaPlayer {
    constructor() {
        this.repeat_mode_list = ["one", "page", "all"];
        this.state = {
            id: null,
            repeat_idx: 1,
            is_moved: false,
            offset: [0, 0],
            width: (+window.localStorage.getItem("player_width")) || 700,
            bottom: null,
        };
        this.mount();
        this.$controller[0].volume = window.localStorage.getItem("player_vol") / 100;
        this.update_size();
        const left = +window.localStorage.getItem("player_left");
        const top = (+window.localStorage.getItem("player_bottom")) - this.$container[0].offsetHeight;
        this.$controller.css("display", window.localStorage.getItem("player_display"));
        this.update_position(left, top);
        const repeat_name = this.repeat_mode_list[this.state.repeat_idx];
        this.$repeat.text(`repeat: ${repeat_name}`);
        this.add_event_listeners()
    }

    get_type() {
        return "media";
    }
    
    get_controller_type(){
        return "audio";
    }

    mount() {
        const ctype = this.get_controller_type();
        const $player = $(`
<div id="player_container">
    <div>
        <${ctype} controls autoplay preload="auto" src="" id="media_controller"></${ctype}>
    </div>
    <div style="width: 100%">
        <div style="width: 100%"></div>
        <button id="prev">prev</button>
        <button id="next">next</button>
        <button id="repeat">repeat</button>
        <button id="hide">hide</button>
        <button id="move">move</button>
        <input id="w" type="number" step="50" min="400" max="${window.innerWidth}" value="${this.state.width}"/>
        <div style="width: 100%"></div>
    </div>
</div>
        `);
        $("body").append($player);
        this.$container = $("#player_container").first();
        this.$controller = $("#media_controller").first();
        this.$next = $("#next").first();
        this.$prev = $("#prev").first();
        this.$repeat = $("#repeat").first();
        this.$hide = $("#hide").first();
        this.$move = $("#move").first();
        this.$width = $("#w").first();
    }

    add_event_listeners() {
        this.$controller.on("play", e => {
            this.update_size();
            let top = this.$container[0].offsetTop;
            if (this.state.bottom !== null)
                top = this.state.bottom - this.$container[0].offsetHeight;
            this.state.bottom = null;
            this.update_position(null, top);
            this.highlight_playing();
        });
        this.$controller.on("pause", e => this.highlight_paused());
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
        this.$controller.on("canplay", e => {
            const $row = this.find_current_row();
            const $dur = $row.find(".field-duration").first();
            if ($dur.length > 0 && $dur.text() === "0:00:00"){
                const duration = this.$controller[0].duration;
                $dur.text(format_duration(duration * 1000));
                this.request_update_duration(duration);
            }
        });
        $(".field-play button").click(e => {
            e.preventDefault();
            const id = $(e.target).data("id");
            const 
                a = this.has_src() * 2,
                b = this.is_current_id(id) * 4,
                c = this.is_paused() * 8;
            switch(1 | a | b | c) {
                case 1 | 2 | 4 | 8:
                    return this.resume();
                case 1 | 2 | 4:
                    return this.pause();
                default:
                    return this.play(id);
            }
        });    
        this.$repeat.click(e => {
            e.preventDefault();
            this.state.repeat_idx = (this.state.repeat_idx + 1) % this.repeat_mode_list.length;
            const repeat_name = this.repeat_mode_list[this.state.repeat_idx];
            $("#repeat").text(`repeat: ${repeat_name}`);
        });
        this.$next.click(e => this.play_next());
        this.$prev.click(e => this.play_prev());
        this.$hide.click(e => {
            const display = this.$controller.css("display");
            let top = this.$container[0].offsetTop;
            const bottom = top + this.$container[0].offsetHeight;
            if (display === "none") {
                this.$controller.css("display", "inline");
                $(e.target).text("hide");
                this.update_size();
                window.localStorage.setItem("player_display", "inline");
            }
            else {
                this.$controller.css("display", "none");
                $(e.target).text("show");
                window.localStorage.setItem("player_display", "none");
            }
            top = bottom - this.$container[0].offsetHeight;
            this.update_position(null, top);
        });
        this.$move.on("mousedown", e => {
            this.state.is_moved = true;
            this.state.offset = [
                this.$container[0].offsetLeft - e.clientX,
                this.$container[0].offsetTop - e.clientY,
            ];
        });
        $(document).on("mouseup", e => {
            this.state.is_moved = false;
            this.state.offset = [0, 0];
        });
        $(document).on("mousemove", e => {
            e.preventDefault();
            if (this.state.is_moved) {
                const left = (e.clientX + this.state.offset[0]);
                const top = (e.clientY + this.state.offset[1]);
                this.update_position(left, top);
            }
        });
        this.$width.on("change", e => {
            this.state.width = e.target.value;
            let top = this.$container[0].offsetTop;
            const bottom = top + this.$container[0].offsetHeight;
            this.update_size();
            top = bottom - this.$container[0].offsetHeight;
            this.update_position(null, top);
            window.localStorage.setItem("player_width", this.state.width);
        });
        $(window).on("resize", e => {
            this.update_size();
            this.update_position();
        });
    }

    update_position(left, top) {
        if (left === undefined || left === null) {
            left = this.$container[0].offsetLeft;
        }
        if (top === undefined || top === null) {
            top = this.$container[0].offsetTop;
        }
        this.$container.css("right", "unset");
        this.$container.css("bottom", "unset");
        const right = left + this.$container[0].offsetWidth;
        const bottom = top + this.$container[0].offsetHeight;
        if (0 <= left && right <= window.innerWidth) {
            left = left;
        }
        else if (left < 0) {
            left = 0;
        }
        else {
            left = window.innerWidth - this.$container[0].offsetWidth;
        }
        this.$container.css("left", left);
        window.localStorage.setItem("player_left", left);
        if (0 <= top && bottom <= window.innerHeight) {
              top = top;
        }
        else if (top < 0) {
            top = 0;
        }
        else {
            top = window.innerHeight - this.$container[0].offsetHeight;
        }
        this.$container.css("top", top);
        window.localStorage.setItem("player_bottom", top + this.$container[0].offsetHeight);
    }

    update_size() {
        let width = this.state.width;
        if (window.innerHeight <= this.$container[0].offsetHeight + 1) {
            const aspect_ratio = this.$container[0].offsetHeight / this.$container[0].offsetWidth;
            const width_to_subtract = (this.$container[0].offsetHeight - window.innerHeight) / aspect_ratio;
            width = Math.round(this.$controller[0].offsetWidth - width_to_subtract);
        }
        // this.$controller.css("width", Math.min(this.$container[0].offsetWidth, width));
        this.$controller.css("width", width);
        this.$width.val(width);
    }

    find_current_row() {
        return $(`.field-play button[data-id="${this.state.id}"]`)
            .parents("tr")
            .first();
    }

    request_update_duration(duration) {
        $.ajax({
            url: window.urls.update_duration,
            type: "POST",
            headers: {'X-CSRFToken': window.get_cookie("csrftoken")},
            dataType: 'json',
            data: {
                id: this.state.id,
                type: this.get_type(),
                duration: duration,
            },
        })
    }

    play(id) {
        let top = this.$container[0].offsetTop;
        this.state.bottom = top + this.$container[0].offsetHeight;
        this.$controller.attr("src", `${window.urls.file_stream}?id=${id}&type=${this.get_type()}`);
        this.state.id = id;
    }

    pause() {
        this.$controller[0].pause();
    }

    resume() {
        this.$controller[0].play();
        this.highlight_playing();
    }

    has_src() {
        return this.$controller.attr("src").length > 0;
    }

    is_paused() {
        return this.$controller[0].paused;
    }

    is_current_id(id) {
        return id == this.state.id;
    }

    play_next() {
        const $row = this.find_current_row();
        let $next_row = $row.next();
        if ($next_row.length == 0) {
            $next_row = $("#result_list tbody tr:first-child").first();
        }
        if ($next_row.length == 0) {
            $next_row = $row;
        }
        if ($next_row.length == 0) {
            $next_row = $("body").first();
        }
        let id = $next_row
            .find(".field-play button")
            .first()
            .data("id");
        this.play(id);
    }

    play_prev(){
        const $row = this.find_current_row();
        let $next_row = $row.prev();
        if ($next_row.length == 0) {
            $next_row = $("#result_list tbody tr:last-child").first();
        }
        if ($next_row.length == 0) {
            $next_row = $row;
        }
        if ($next_row.length == 0) {
            $next_row = $("body").first();
        }
        let id = $next_row
            .find(".field-play button")
            .first()
            .data("id");
        this.play(id);
    }

    highlight_playing(){
        $("#result_list tr button").text("play");
        $("#result_list tr.playing").removeClass("playing");
        $("#result_list tr.paused").removeClass("paused");
        const $button = $(`.field-play button[data-id="${this.state.id}"]`).first();
        $button.text("pause");
        const $row = $button.parents("tr").first();
        $row.addClass("playing");
    }

    highlight_paused(){
        $("#result_list tr button").text("play");
        $("#result_list tr.playing").removeClass("playing");
        $("#result_list tr.paused").removeClass("paused");
        const $button = $(`.field-play button[data-id="${this.state.id}"]`).first();
        $button.text("play");
        const $row = $button.parents("tr").first();
        $row.addClass("paused");
    }
}


