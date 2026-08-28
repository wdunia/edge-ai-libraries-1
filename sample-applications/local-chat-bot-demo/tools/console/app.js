const TOKEN = document.querySelector('meta[name="demo-token"]').content;
const DRAFT_KEY = 'local-chat-bot-demo.draft';
const LABELS = { chatgpt: 'ChatGPT', local: 'Local Chat Bot' };

const promptField = document.getElementById('prompt');
const examples = document.getElementById('examples');
const notice = document.getElementById('notice');
const sendButton = document.getElementById('send');

function setNotice(message, state = 'info') {
    notice.textContent = message;
    notice.dataset.state = state;
}

function setStatus(target, state, detail) {
    const pill = document.getElementById(`status-${target}`);
    if (!pill) {
        return;
    }
    pill.dataset.state = state;
    pill.textContent = `${LABELS[target]}: ${state}`;
    pill.title = detail || '';
}

async function post(path, body = {}) {
    const response = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Demo-Token': TOKEN },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error || `request failed with status ${response.status}`);
    }
    return response;
}

async function send() {
    const text = promptField.value.trim();
    if (!text) {
        return;
    }
    sendButton.disabled = true;
    try {
        await post('/api/prompt', { text });
        promptField.value = '';
        localStorage.removeItem(DRAFT_KEY);
        examples.value = '';
        setNotice('');
    } catch (error) {
        setNotice(error.message, 'error');
    } finally {
        sendButton.disabled = false;
        promptField.focus();
    }
}

async function command(path, message) {
    try {
        await post(path);
        setNotice(message);
    } catch (error) {
        setNotice(error.message, 'error');
    }
}

document.getElementById('composer').addEventListener('submit', (event) => {
    event.preventDefault();
    send();
});

promptField.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        send();
    }
});

promptField.addEventListener('input', () => {
    localStorage.setItem(DRAFT_KEY, promptField.value);
});

examples.addEventListener('change', () => {
    if (!examples.value) {
        return;
    }
    promptField.value = examples.value;
    localStorage.setItem(DRAFT_KEY, promptField.value);
    promptField.focus();
});

document.getElementById('relayout').addEventListener('click', () => {
    command('/api/relayout', 'Rearranging windows...');
});

document.getElementById('reset').addEventListener('click', () => {
    if (confirm('Start a new conversation in both chatbots? The current conversations will be lost.')) {
        command('/api/reset', 'Starting new conversations...');
    }
});

document.getElementById('shutdown').addEventListener('click', () => {
    if (confirm('Shut down the demo? All browser windows will be closed.')) {
        command('/api/shutdown', 'Shutting down...');
    }
});

function connectEvents() {
    const stream = new EventSource('/api/events');

    stream.onmessage = (event) => {
        const { target, state, detail } = JSON.parse(event.data);
        if (target in LABELS) {
            setStatus(target, state, detail);
        }
        if (detail) {
            setNotice(detail, state === 'error' ? 'error' : 'info');
        }
    };

    // The stream ends whenever the automation loop restarts; keep the console usable.
    stream.onerror = () => {
        stream.close();
        setTimeout(connectEvents, 2000);
    };
}

async function loadExamples() {
    try {
        const response = await fetch('/api/examples');
        const { examples: items } = await response.json();
        for (const text of items) {
            const option = document.createElement('option');
            option.value = text;
            option.textContent = text.length > 70 ? `${text.slice(0, 70)}...` : text;
            option.title = text;
            examples.appendChild(option);
        }
    } catch {
        setNotice('Could not load example prompts.', 'error');
    }
}

promptField.value = localStorage.getItem(DRAFT_KEY) || '';
loadExamples();
connectEvents();
promptField.focus();
