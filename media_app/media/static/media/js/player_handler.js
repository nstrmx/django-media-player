const state = {
    player: null,
    media_type: null,
    channel: null,
    playing_interval: null,
};

$(window).on("load", e => {
    state.channel = new BroadcastChannel("django-player");

    state.channel.onmessage = (e) => {
        if (!e.data) return;

        if (e.data.action === "ping") {
            state.channel.postMessage({action: "pong"});
            return;
        }

        if (e.data.action === "status_request") {
            if (state.player && state.player.state.id && !state.player.is_paused()) {
                state.channel.postMessage({
                    action: "playing",
                    media: { type: state.media_type, id: state.player.state.id }
                });
            }
            return;
        }

        if (e.data.action === "play") {
            state.media_type = e.data.media_type;
            if (!state.player || state.player.media_type !== e.data.media_type) {
                switch (e.data.media_type) {
                    case "radio":
                    case "audio":
                        window.resizeTo(400, 150);
                        break;
                    case "video":
                        window.resizeTo(600, 450);
                        break;
                }
                state.player = new MediaPlayer(state);
            }
            state.player.state.playlist = e.data.playlist || [];
            state.player.play(e.data.media_id);

            // Confirm playback
            state.channel.postMessage({
                action: "playing",
                media: { type: e.data.media_type, id: e.data.media_id }
            });

            // Periodically resend status
            if (state.playing_interval) clearInterval(state.playing_interval);
            state.playing_interval = setInterval(() => {
                if (state.player && state.player.state.id && !state.player.is_paused()) {
                    state.channel.postMessage({
                        action: "playing",
                        media: { type: state.media_type, id: state.player.state.id }
                    });
                }
            }, 500);
        }
    };

    // Signal ready
    state.channel.postMessage({action: "ready"});
});
