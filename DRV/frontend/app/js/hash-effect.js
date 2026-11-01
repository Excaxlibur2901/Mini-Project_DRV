/**
 * Client-Side Hashing & Visual Hash Comparison Effects
 * Conforms to DESIGN.md §3.2 & §5
 */

/**
 * Compute SHA-256 hex string directly in the browser via Web Crypto API.
 */
export async function computeClientSHA256(file) {
  const arrayBuffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Format 64-character hash into 8-character space-separated groups.
 */
export function formatHashChunks(hexStr) {
  if (!hexStr) return '';
  return hexStr.match(/.{1,8}/g).join(' ');
}

/**
 * Visual resolve effect: fills characters from left to right over ms duration.
 */
export function resolveHashEffect(element, finalHex, ms = 700) {
  const hexChars = '0123456789abcdef';
  const start = performance.now();

  return new Promise((resolve) => {
    function tick(now) {
      const progress = Math.min((now - start) / ms, 1);
      const lockedChars = Math.floor(progress * finalHex.length);
      const randomTail = Array.from(
        { length: finalHex.length - lockedChars },
        () => hexChars[Math.floor(Math.random() * 16)]
      ).join('');

      element.textContent = formatHashChunks(finalHex.slice(0, lockedChars) + randomTail);

      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        element.textContent = formatHashChunks(finalHex);
        resolve();
      }
    }
    requestAnimationFrame(tick);
  });
}

/**
 * Generate side-by-side character comparison HTML highlighting differences.
 */
export function generateHashComparisonHtml(computed, registered) {
  let computedHtml = '';
  let registeredHtml = '';

  const len = Math.max(computed.length, registered.length);
  for (let i = 0; i < len; i++) {
    const c1 = computed[i] || '';
    const c2 = registered[i] || '';
    const match = c1.toLowerCase() === c2.toLowerCase();

    if (match) {
      computedHtml += `<span class="hash-match">${c1}</span>`;
      registeredHtml += `<span class="hash-match">${c2}</span>`;
    } else {
      computedHtml += `<span class="hash-diff">${c1}</span>`;
      registeredHtml += `<span class="hash-diff">${c2}</span>`;
    }

    if ((i + 1) % 8 === 0 && i + 1 < len) {
      computedHtml += ' ';
      registeredHtml += ' ';
    }
  }

  return { computedHtml, registeredHtml };
}

