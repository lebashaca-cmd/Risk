let toastTimer;
export function toast(message) {
    const el = document.getElementById("toast");
    if (!el)
        return;
    el.textContent = message;
    el.classList.add("show");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => el.classList.remove("show"), 1800);
}
export async function copyText(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    }
    catch {
        const area = document.createElement("textarea");
        area.value = text;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        let ok = false;
        try {
            ok = document.execCommand("copy");
        }
        catch {
            ok = false;
        }
        area.remove();
        return ok;
    }
}
export async function copyWithToast(text) {
    toast((await copyText(text)) ? "Copied to clipboard" : "Couldn't copy. Select the text and copy it yourself.");
}
export function flashCopied(button) {
    button.classList.add("copied");
    window.setTimeout(() => button.classList.remove("copied"), 1100);
}
