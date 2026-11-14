// The "checking that you're a person" page. Cloudflare Turnstile calls riskGateDone once the visitor passes.
// The widget and button close straight away, a short "verified" line takes their place, and the form posts the
// token to /verify-human, which sets the pass cookie and sends them on to the page they asked for.
declare global {
  interface Window {
    riskGateDone?: () => void;
  }
}

window.riskGateDone = () => {
  const form = document.getElementById("gate-form") as HTMLFormElement | null;
  if (!form) return;
  const token = form.querySelector<HTMLInputElement>('[name="cf-turnstile-response"]');
  if (token && !token.value) return;
  form.querySelector<HTMLElement>(".cf-turnstile")?.setAttribute("hidden", "");
  form.querySelector<HTMLElement>("button[type=submit]")?.setAttribute("hidden", "");
  const heading = document.querySelector<HTMLElement>("#gate h1");
  const lede = document.querySelector<HTMLElement>("#gate .lede");
  if (heading) heading.textContent = "You're verified";
  if (lede) lede.textContent = "Taking you to the page now.";
  document.getElementById("gate")?.setAttribute("aria-busy", "true");
  form.requestSubmit();
};

export {};
