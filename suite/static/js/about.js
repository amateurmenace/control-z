/* About — what this is, who it's for, and the receipts.
   The story in a few paragraphs, the covenant with its meanings, the same
   credits the website's footer carries, and this build's own numbers. */

const AboutPage = (() => {
  const el = document.createElement("div");
  el.className = "page";
  el.id = "page-about";

  const COVENANT = [
    ["free forever", "MIT licensed, no tiers, no trials, no 'pro' version waiting behind a card"],
    ["works with free Resolve", "every export lands in the free version — nothing assumes Studio"],
    ["local only", "your footage never leaves this machine; no accounts, no telemetry"],
    ["shows its work", "every tool keeps a measurement surface on — you can see what it did"],
    ["honest limitations", "each tool names what the paid alternative still does better"],
  ];

  function render() {
    const info = CZ.appInfo || {};
    const hw = (info.presets || []).filter(p => p.available && p.hardware).length;
    el.innerHTML = `<div class="page-pad" style="max-width:760px">
      <div class="tag">community ai project</div>
      <h1 style="margin-top:6px">About</h1>

      <div class="about-story">
        <p><b>control-z</b> is a free, open-source workbench around the free version of
        DaVinci Resolve — cleaning, prepping, making, and finishing tools for community
        media centers, journalists, filmmakers, and artists. The name is the promise:
        <i>undo the paywall.</i> The features that hide behind Studio licenses and
        per-seat subscriptions, rebuilt to run on your machine, on your footage,
        for nothing.</p>

        <p>The suite grew up at <a href="https://brooklineinteractive.org" target="_blank" rel="noopener">Brookline
        Interactive Group</a>, a public-access station, which is why it thinks like one:
        Grabber fetches the town's meetings off the civic portal, Highlighter cuts them
        down to the moments residents actually need to see, Slate makes the lower thirds
        and leaders every program deserves, and Index remembers where all of it lives.
        Those first two began life as BIG's own community apps —
        <i>community-highlighter</i> and <i>BIG Video Grabber</i> — and were rebuilt here
        on the suite's local engine: same jobs, no cloud, no API keys.</p>

        <p>Every AI model in the suite is permissively licensed, hash-verified on
        download, and listed on the Models page with a remove button. The only network
        this app touches is the network you ask for: fetching a video, checking the
        yt-dlp nightly, downloading a model. Nothing phones home.</p>
      </div>

      <div class="insp-sec" style="margin-top:22px">
        <span class="tag">the covenant</span>
        <div class="about-covenant">
          ${COVENANT.map(([k, v]) => `<div class="cov-row"><b>${k}</b><span>${v}</span></div>`).join("")}
        </div>
      </div>

      <div class="insp-sec">
        <span class="tag">this build</span>
        <div class="about-build">
          version <b>${esc(info.version || "?")}</b> · ${esc(info.platform || "")} ·
          ${hw} hardware encoder preset${hw === 1 ? "" : "s"} live ·
          ten tools + the queue, one window
        </div>
      </div>

      <div class="insp-sec">
        <span class="tag">from the website's footer</span>
        <div class="about-footer">
          <div>control-z · undo the paywall</div>
          <div>Designed and developed by <a href="https://weirdmachine.org" target="_blank" rel="noopener">Stephen Walter</a>
            and Claude Code · 2026</div>
          <div><b>the covenant:</b> free forever (MIT) · works with free Resolve ·
            local only · shows its work · honest limitations</div>
          <p>An open-source tool of the
            <a href="https://communityai.studio" target="_blank" rel="noopener">Community AI Project</a>,
            made in partnership with
            <a href="https://brooklineinteractive.org" target="_blank" rel="noopener">Brookline Interactive Group</a>.
            Every model in the suite is permissively licensed, hash-verified, and runs on
            your machine — nothing phones home. Released under the
            <a href="https://opensource.org/license/mit" target="_blank" rel="noopener">MIT license</a>.</p>
          <p>Every demo frame on the site is real output from the tools, run on
            freely-licensed footage from
            <a href="https://www.pexels.com/license/" target="_blank" rel="noopener">Pexels</a> —
            thanks to Ivan&nbsp;S, Antonius&nbsp;Ferret, August&nbsp;de&nbsp;Richelieu and
            MART&nbsp;PRODUCTION. Hush's before/after is its own synthetic validation card.</p>
        </div>
      </div>

      <div class="insp-sec">
        <span class="tag">elsewhere</span>
        <div class="about-links">
          <a href="https://control-z.org" target="_blank" rel="noopener">control-z.org</a>
          <a href="https://github.com/amateurmenace/control-z" target="_blank" rel="noopener">source on GitHub</a>
          <a href="https://github.com/amateurmenace/Hush-OpenNR" target="_blank" rel="noopener">Hush (denoise OpenFX)</a>
          <a href="https://github.com/amateurmenace/Speak" target="_blank" rel="noopener">Speak (film character OpenFX)</a>
        </div>
      </div>

      <div class="covenant-line">free forever · runs with free resolve · local only ·
        shows its work · honest limitations</div>
    </div>`;
  }

  function onshow() { render(); }
  registerPage("about", el, onshow);
  return { onshow };
})();
