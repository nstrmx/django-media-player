const state = {
    key: null,
    worker: null,
    is_open: null,
    last_media: null,
    playlist: null,
}

const handler = {
    connect_to_worker: function () {
        const self = this;
        state.worker = new SharedWorker(global.urls.worker_src_url, "Django Player");
        state.worker.port.start();
        state.key = state.key || this.make_key(8);
        state.worker.port.postMessage({
            action: "host:register",
            key: state.key,
        });
        state.worker.port.addEventListener("message", e => {
            this.handle_message(e.data);
        });
    },

    make_key: function (length) {
        let result = [];
        const characters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        const chars_length = characters.length;
        for (let i = 0; i < length; i++) {
            result.push(
                characters.charAt(Math.floor(Math.random() * chars_length))
            );
        }
        return result.join("");
    },

    handle_message: function (data) {
        if (!data) {
            return;
        }
        switch (data.action) {
        case "worker:player_status": 
            switch (data.status) {
            case "open":
                state.is_open = true;
                if (state.last_media) {
                    handler.change_media(state.last_media);
                }
                break;
            case "closed":
                state.is_open = false;
                break;
            case "playing":
                if (data.media_type === window.media_type) {
                    const $item = $(`.field-play button[data-id=${data.media.id}]`).first();
                    const desc = $item.parents("tr").find(".field-title a").first().text();
                    state.last_media = {
                        id: data.media.id,
                        desc: desc,
                    };
                    this.highlight_playing();
                }
                break;
            case "paused":
                if (data.media_type === window.media_type) {
                    const $item = $(`.field-play button[data-id=${data.media.id}]`).first();
                    const desc = $item.parents("tr").find(".field-title a").first().text();
                    state.last_media = {
                        id: data.media.id,
                        desc: desc,
                    };
                    this.highlight_paused();
                }
                break;
            };
            break;
        // case 
        // case "resume_media":
        //     this.change_media(data.media_id);
        //     break;
        }
    },

    open_player_window: function () {
        if (state.is_open) {
            return;
        }
        window.open(
            global.urls.player, 
            "Django Player", 
            "allow=autoplay, toolbar=no, scrollbars=no, resizable=no"
            + "width=100, height=100"
        );
    },

    change_media: function (media) {
        const self = this;
        state.worker.port.postMessage({
            action: "host:play",
            key: state.key,
            media_id: media.id,
            media_type: global.media_type,
            media_desc: media.desc,
            playlist: self.load_playlist(),
        });
        state.last_media = media;
    },

    load_playlist: function() {
        const playlist = Array.from(
            $(".field-play button").map(function() {
                const media = {};
                const $item = $(this);
                media.id = $item.data("id");
                media.tile = $item.parents("tr").find(".field-title a").first().text();
                return media;
            })
        );
        return playlist;
    },

    highlight_playing: function() {
        $("#result_list tr button").text("play");
        $("#result_list tr.playing").removeClass("playing");
        $("#result_list tr.paused").removeClass("paused");
        const $button = $(`.field-play button[data-id="${state.last_media.id}"]`).first();
        $button.text("pause");
        const $row = $button.parents("tr").first();
        $row.addClass("playing");
    },

    highlight_paused: function() {
        $("#result_list tr button").text("play");
        $("#result_list tr.playing").removeClass("playing");
        $("#result_list tr.paused").removeClass("paused");
        const $button = $(`.field-play button[data-id="${state.last_media.id}"]`).first();
        $button.text("play");
        const $row = $button.parents("tr").first();
        $row.addClass("paused");
    }
};

$(window).on("load", e => {
    handler.connect_to_worker();
    state.playlist = handler.load_playlist();
});

$(document).on("click", ".field-play button", e => {
    e.preventDefault();
    handler.open_player_window();
    const $item = $(e.target);
    const media = {
        id: $item.data("id"),
        desc: $item.parents("tr").find(".field-title a").first().text(),
    };
    if (state.is_open) {
        handler.change_media(media);
    } else {
        state.last_media = media;
    }
}); 

$(window).on("beforeunload", e => {
    state.worker.port.postMessage({
        action: "host:unregister",
    });
});