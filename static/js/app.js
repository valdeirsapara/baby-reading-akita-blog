function getCookie(name) {
    let value = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                value = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return value;
}

const CSRF_TOKEN = document.querySelector('input[name=csrfmiddlewaretoken]')?.value || getCookie('csrftoken');

async function api(url, { method = 'GET', body = null } = {}) {
    const opts = {
        method,
        headers: {
            'X-CSRFToken': CSRF_TOKEN,
            'X-Requested-With': 'XMLHttpRequest',
        },
    };
    if (body !== null) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
    }
    const resp = await fetch(url, opts);
    return resp.json();
}

const controllers = {};
function registerController(name, setup) {
    controllers[name] = setup;
}


const VueApp = {
    mount(name) {
        const el = document.getElementById('app');
        if (!name || !controllers[name]) {
            console.warn('Controller não encontrado:', name);
            return;
        }
        Vue.createApp({
            delimiters: ['[[', ']]'],
            setup() {
                // injeta o api() em todos os controllers, como o $http era injetado
                const ctx = controllers[name](Vue);
                return { api, ...ctx };
            },
        }).mount(el);
    },
};
