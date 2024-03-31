function get_cookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

function format_duration(duration) {
    const h = Math.floor((duration % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const m = Math.floor((duration % (1000 * 60 * 60)) / (1000 * 60));
    const s = Math.floor((duration % (1000 * 60)) / 1000);
    const hh = `${+(h>9)?"":0}${h}`;
    const mm = `${(m>9)?"":0}${m}`;
    const ss = `${(s>9)?"":0}${s}`
    return `${hh}:${mm}:${ss}`;
}

window.$ = window.django.jQuery;
window.urls = {};
