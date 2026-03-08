/**
 * 1-based index → 알파벳 레이블 변환
 * 1→a, 26→z, 27→aa, 28→ab, ...
 */
export function idxToLabel(n: number): string {
  let result = '';
  while (n > 0) {
    n--;
    result = String.fromCharCode(97 + (n % 26)) + result;
    n = Math.floor(n / 26);
  }
  return result;
}
