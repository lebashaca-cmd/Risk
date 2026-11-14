window.riskGateDone = () => {
    const form = document.getElementById("gate-form");
    if (!form)
        return;
    const token = form.querySelector('[name="cf-turnstile-response"]');
    if (token && !token.value)
        return;
    form.querySelector(".cf-turnstile")?.setAttribute("hidden", "");
    form.querySelector("button[type=submit]")?.setAttribute("hidden", "");
    const heading = document.querySelector("#gate h1");
    const lede = document.querySelector("#gate .lede");
    if (heading)
        heading.textContent = "You're verified";
    if (lede)
        lede.textContent = "Taking you to the page now.";
    document.getElementById("gate")?.setAttribute("aria-busy", "true");
    form.requestSubmit();
};
export {};
