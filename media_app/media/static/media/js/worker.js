const state = {
    player_port: null,
    host_window_ports: {},
    player_status: null,
    current_media: null,
};


onconnect = function (e) {
    const port = e.ports[0];
    port.onmessage = function (event) {
        const data = event.data;
        switch (data.action) {
            case "host:register":
                state.host_window_ports[data.key] = port;
                post_player_status(port);
                break;
            case "host:unregister":
                delete state.host_window_ports[data.key];
                break;
            case "host:play":
                if (!state.player_port) {
                    return;
                }
                state.player_port.postMessage(data);
                break;
            case "host:player_status":
                post_player_status(port);
                break;
            case "player:register":
                state.player_port = port;
                state.player_status = "open";
                broadcast_player_status();
                break;
            case "player:unregister":
                state.player_port = null;
                state.player_status = "closed";
                broadcast_player_status();
                break;
            case "player:play":
                state.player_status = "playing";
                state.current_media = data.media;
                broadcast_player_status();
                break;
            case "player:pause":
                state.player_status = "paused";
                state.current_media = data.media;
                broadcast_player_status();
                break;
        }
    };
};

function post_player_status(port) {
    const data = {
        action: "worker:player_status",
        status: state.player_status,
    };
    if (data.status === "playing" || data.status === "paused") {
        data.media = state.current_media;
    }
    port.postMessage(data);
}

function broadcast_player_status() {
    for (let [key, port] of Object.entries(state.host_window_ports)) {
        post_player_status(port);
    }
}