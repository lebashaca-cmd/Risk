// The "checking that you're a person" page. Cloudflare Turnstile calls riskGateDone once the visitor passes,
// and the form then posts the token to /verify-human, which sets the pass cookie and sends them on.
declare global {
  interface Window {
    riskGateDone?: () => void;
  }
}

window.riskGateDone = () => {
  const form = document.getElementById("gate-form") as HTMLFormElement | null;
  form?.requestSubmit();
};

export {};
