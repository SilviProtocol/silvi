// Custom CSS for driver.js — Treekipedia dark emerald frosted-glass theme
export const tourStyles = `
  /* ===== POPOVER CONTAINER ===== */
  .driver-popover.treekipedia-tour {
    background: rgba(10, 15, 12, 0.95);
    border: 1px solid rgba(16, 185, 129, 0.4);
    border-radius: 16px;
    color: #ffffff;
    font-family: 'Montserrat', sans-serif;
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    box-shadow:
      0 0 40px rgba(16, 185, 129, 0.12),
      0 8px 32px rgba(0, 0, 0, 0.5),
      inset 0 1px 0 rgba(110, 231, 183, 0.1);
    padding: 20px 24px;
    max-width: 400px;
    min-width: 320px;
  }

  /* ===== TITLE ===== */
  .driver-popover.treekipedia-tour .driver-popover-title {
    font-family: 'Montserrat', sans-serif;
    font-size: 1.15rem;
    font-weight: 700;
    color: #6ee7b7;
    letter-spacing: -0.01em;
    margin-bottom: 4px;
  }

  /* ===== DESCRIPTION ===== */
  .driver-popover.treekipedia-tour .driver-popover-description {
    font-family: 'Montserrat', sans-serif;
    font-size: 0.9rem;
    line-height: 1.65;
    color: rgba(255, 255, 255, 0.85);
    margin-top: 6px;
  }

  /* ===== PROGRESS TEXT ===== */
  .driver-popover.treekipedia-tour .driver-popover-progress-text {
    font-family: 'Montserrat', sans-serif;
    font-size: 0.75rem;
    color: rgba(110, 231, 183, 0.5);
    font-weight: 500;
  }

  /* ===== FOOTER ===== */
  .driver-popover.treekipedia-tour .driver-popover-footer {
    margin-top: 16px;
    gap: 8px;
  }

  .driver-popover.treekipedia-tour .driver-popover-navigation-btns {
    gap: 8px;
  }

  /* ===== NEXT / DONE BUTTON ===== */
  .driver-popover.treekipedia-tour .driver-popover-next-btn {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: #ffffff;
    border: none;
    border-radius: 10px;
    font-family: 'Montserrat', sans-serif;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 8px 20px;
    text-shadow: none;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
  }

  .driver-popover.treekipedia-tour .driver-popover-next-btn:hover {
    background: linear-gradient(135deg, #34d399 0%, #10b981 100%);
    box-shadow: 0 4px 16px rgba(16, 185, 129, 0.4);
    transform: translateY(-1px);
  }

  /* ===== BACK BUTTON ===== */
  .driver-popover.treekipedia-tour .driver-popover-prev-btn {
    background: rgba(255, 255, 255, 0.06);
    color: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 10px;
    font-family: 'Montserrat', sans-serif;
    font-weight: 500;
    font-size: 0.85rem;
    padding: 8px 16px;
    text-shadow: none;
    transition: all 0.2s ease;
  }

  .driver-popover.treekipedia-tour .driver-popover-prev-btn:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.3);
  }

  /* ===== CLOSE BUTTON (X) ===== */
  .driver-popover.treekipedia-tour .driver-popover-close-btn {
    color: rgba(255, 255, 255, 0.3);
    font-size: 18px;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    transition: all 0.2s ease;
  }

  .driver-popover.treekipedia-tour .driver-popover-close-btn:hover {
    color: rgba(255, 255, 255, 0.8);
    background: rgba(255, 255, 255, 0.08);
  }

  /* ===== ARROWS — match popover background ===== */
  .driver-popover.treekipedia-tour.driver-popover-arrow-side-left .driver-popover-arrow {
    border-left-color: rgba(10, 15, 12, 0.95);
  }
  .driver-popover.treekipedia-tour.driver-popover-arrow-side-right .driver-popover-arrow {
    border-right-color: rgba(10, 15, 12, 0.95);
  }
  .driver-popover.treekipedia-tour.driver-popover-arrow-side-top .driver-popover-arrow {
    border-top-color: rgba(10, 15, 12, 0.95);
  }
  .driver-popover.treekipedia-tour.driver-popover-arrow-side-bottom .driver-popover-arrow {
    border-bottom-color: rgba(10, 15, 12, 0.95);
  }

  /* ===== HIGHLIGHT STAGE — emerald glow ===== */
  .driver-active-element {
    border-radius: 12px !important;
  }

  /* ===== PREVENT PAGE SCROLL during tour ===== */
  /* driver.js calls scrollIntoView() internally which fights
     with fixed-position elements and Leaflet maps, causing
     infinite scroll loops that crash the browser. */
  html.driver-active {
    overflow: hidden !important;
    scroll-behavior: auto !important;
  }
  html.driver-active body {
    overflow: hidden !important;
  }
`;
