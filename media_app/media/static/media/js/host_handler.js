const state = {
    channel: null,
    last_media: null,
    playlist: null,
    player_responded: false,
};

const handler = {
    connect_to_channel: function () {
        state.channel = new BroadcastChannel("django-player");
        state.channel.onmessage = (e) => {
            if (!e.data) return;
            if (e.data.action === "pong") {
                state.player_responded = true;
            }
            if (e.data.action === "ready") {
                // Popup is ready, trigger any pending play
                if (state.pending_play) {
                    handler.play_media(state.pending_play);
                    state.pending_play = null;
                }
            }
            if (e.data.action === "playing") {
                if (e.data.media && e.data.media.type === global.media_type) {
                    handler.highlight_playing(e.data.media);
                }
            }
            if (e.data.action === "paused") {
                if (e.data.media && e.data.media.type === global.media_type) {
                    handler.highlight_paused(e.data.media);
                }
            }
        };
    },

    load_playlist: function() {
        const playlist = Array.from(
            $(".field-play button").map(function() {
                const media = {};
                const $item = $(this);
                media.id = $item.data("id");
                media.title = $item.parents("tr").find(".field-title a").first().text();
                return media;
            })
        );
        return playlist;
    },

    play_media: function (media) {
        state.channel.postMessage({
            action: "play",
            media_id: media.id,
            media_type: global.media_type,
            media_desc: media.desc,
            playlist: handler.load_playlist(),
        });
        state.last_media = media;
    },

    highlight_playing: function(media) {
        $("#result_list tr button").text("play");
        $("#result_list tr.playing").removeClass("playing");
        $("#result_list tr.paused").removeClass("paused");
        const $button = $(`.field-play button[data-id="${media.id}"]`).first();
        if ($button.length) {
            $button.text("pause");
            const $row = $button.parents("tr").first();
            $row.addClass("playing");
        }
    },

    highlight_paused: function(media) {
        $("#result_list tr button").text("play");
        $("#result_list tr.playing").removeClass("playing");
        $("#result_list tr.paused").removeClass("paused");
        const $button = $(`.field-play button[data-id="${media.id}"]`).first();
        if ($button.length) {
            $button.text("play");
            const $row = $button.parents("tr").first();
            $row.addClass("paused");
        }
    }
};

$(window).on("load", e => {
    handler.connect_to_channel();
    state.playlist = handler.load_playlist();
    // Request current status
    state.channel.postMessage({action: "status_request"});
});

$(document).on("click", ".field-play button", e => {
    e.preventDefault();
    const $item = $(e.target);
    const media = {
        id: $item.data("id"),
        desc: $item.parents("tr").find(".field-title a").first().text(),
    };

    if ($item.text() === "pause") {
        state.channel.postMessage({
            action: "pause",
            media_id: media.id,
        });
        state.last_media = media;
    } else {
        state.player_responded = false;
        state.channel.postMessage({action: "ping"});

        setTimeout(() => {
            if (!state.player_responded) {
                window.open(
                    global.urls.player,
                    "Django Player",
                    "allow=autoplay, toolbar=no, scrollbars=no, resizable=no"
                );
                state.pending_play = media;
            } else {
                handler.play_media(media);
            }
        }, 200);
    }
});
