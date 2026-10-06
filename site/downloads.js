// Only advertise executable assets that actually exist in the published release.
(async () => {
  try {
    const response = await fetch('https://api.github.com/repos/ProfEngel/TrinityLectureAssisitant/releases/tags/v0.19.1', {cache:'no-cache'});
    if (!response.ok) return;
    const release = await response.json();
    if (release.draft || release.prerelease) return;
    let count = 0;
    document.querySelectorAll('[data-asset]').forEach(link => {
      const asset = release.assets.find(item => item.name.endsWith(link.dataset.asset));
      if (asset) { link.href = asset.browser_download_url; count += 1; }
    });
    document.getElementById('build-status').textContent = count === 3 ? 'Mac-DMG, Windows-Setup und Portable ZIP verfügbar. SHA256-Prüfsummen im Release.' : 'Einige Plattform-Builds sind noch in Vorbereitung. Das Release zeigt die bereits verfügbaren Downloads.';
  } catch (_) { /* A GitHub API limit never hides the normal release links. */ }
})();
