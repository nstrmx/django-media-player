const state = {
    player: null,
    worker: null,
    media_type: null,
};

const handle_message = e => {
    if (!e.data) {
        return;
    }
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
    state.player.state.playlist = e.data.playlist;
    state.player.play(e.data.media_id);
}

$(window).on("load", e => {
    state.worker = new SharedWorker(global.urls.worker_src_url, "Django Player");
    state.worker.port.start();
    state.worker.port.addEventListener("message", handle_message);
    state.worker.port.postMessage({
        action: "player:register",
    });
});

$(window).on("player:play", (e, data) => {
    state.worker.port.postMessage({
        action: "player:play",
        ...data
    });
});

$(window).on("player:pause", (e, data) => {
    state.worker.port.postMessage({
        action: "player:pause",
        ...data
    });
});

$(window).on("player:resume", (e, data) => {
    state.worker.port.postMessage({
        action: "player:resume",
        ...data
    });
});

$(window).on("beforeunload", () => {
    worker.port.postMessage({
        action: "player:unregister",
    });
});