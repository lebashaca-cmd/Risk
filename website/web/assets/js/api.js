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
};
