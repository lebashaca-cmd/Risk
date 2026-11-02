async function getJSON(path) {
    const res = await fetch(path, { headers: { Accept: "application/json" } });
    if (!res.ok)
        throw new Error(`${path} answered ${res.status}`);
    return (await res.json());
}
export const api = {
    config: () => getJSON("/api/config"),
    status: () => getJSON("/api/status"),
    commands: () => getJSON("/api/commands"),
    tos: () => getJSON("/api/tos"),
    privacy: () => getJSON("/api/privacy"),
};
export class ApiFailure extends Error {
    status;
    constructor(message, status) {
        super(message);
        this.status = status;
    }
}
async function send(method, path, body) {
    let res;
    try {
        res = await fetch(path, {
            method,
            credentials: "same-origin",
            headers: { Accept: "application/json", "X-Requested-With": "risk", ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
            body: body === undefined ? undefined : JSON.stringify(body),
        });
    }
    catch {
        throw new ApiFailure("Couldn't reach the site. Check your connection and try again.", 0);
    }
    let payload = null;
    try {
        payload = await res.json();
    }
    catch {
        payload = null;
    }
    if (!res.ok) {
        const message = payload && typeof payload === "object" && "error" in payload && typeof payload.error === "string" ? payload.error : `The request failed (${res.status}).`;
        throw new ApiFailure(message, res.status);
    }
    return payload;
}
export const dashApi = {
    me: () => send("GET", "/api/auth/me"),
    guild: (id) => send("GET", `/api/dash/guild/${encodeURIComponent(id)}`),
    save: (id, section, body) => send("PUT", `/api/dash/guild/${encodeURIComponent(id)}/${section}`, body),
    logout: () => send("POST", "/api/auth/logout"),
};
