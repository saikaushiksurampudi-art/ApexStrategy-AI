import '@testing-library/jest-dom/vitest'

// jsdom implements neither of these, and both are used by the motion layer.
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
}

if (!('IntersectionObserver' in window)) {
  class StubIntersectionObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return []
    }
    root = null
    rootMargin = ''
    thresholds = []
  }
  // @ts-expect-error -- test stub
  window.IntersectionObserver = StubIntersectionObserver
}
