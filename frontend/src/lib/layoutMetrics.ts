/**
 * Pixels of the map covered by UI at the bottom (mobile sheet + slider). Read by the map camera
 * when fitting bounds; written by the bottom sheet whenever it snaps. Not React state.
 */
let bottomInsetPx = 0;

export function setMapBottomInset(px: number): void {
  bottomInsetPx = Math.max(0, Math.round(px));
}

export function mapBottomInset(): number {
  return bottomInsetPx;
}
