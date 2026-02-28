// Custom CSS for Treekipedia tour — dark emerald frosted-glass theme
// No external library dependency — pure React + CSS
export const tourStyles = `
  /* ===== POPOVER ===== */
  .treekipedia-tour-popover {
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
    min-width: 300px;
    pointer-events: auto;
  }

  /* ===== TITLE ===== */
  .treekipedia-tour-popover .tour-title {
    font-size: 1.15rem;
    font-weight: 700;
    color: #6ee7b7;
    letter-spacing: -0.01em;
    margin-bottom: 6px;
    padding-right: 28px;
  }

  /* ===== DESCRIPTION ===== */
  .treekipedia-tour-popover .tour-description {
    font-size: 0.9rem;
    line-height: 1.65;
    color: rgba(255, 255, 255, 0.85);
  }

  /* ===== FOOTER ===== */
  .treekipedia-tour-popover .tour-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 16px;
  }

  .treekipedia-tour-popover .tour-progress {
    font-size: 0.75rem;
    color: rgba(110, 231, 183, 0.5);
    font-weight: 500;
  }

  .treekipedia-tour-popover .tour-nav-btns {
    display: flex;
    gap: 8px;
  }

  /* ===== NEXT / DONE BUTTON ===== */
  .treekipedia-tour-popover .tour-btn-next {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%);
    color: #ffffff;
    border: none;
    border-radius: 10px;
    font-family: 'Montserrat', sans-serif;
    font-weight: 600;
    font-size: 0.85rem;
    padding: 8px 20px;
    cursor: pointer;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
  }

  .treekipedia-tour-popover .tour-btn-next:hover {
    background: linear-gradient(135deg, #34d399 0%, #10b981 100%);
    box-shadow: 0 4px 16px rgba(16, 185, 129, 0.4);
    transform: translateY(-1px);
  }

  /* ===== BACK BUTTON ===== */
  .treekipedia-tour-popover .tour-btn-back {
    background: rgba(255, 255, 255, 0.06);
    color: rgba(255, 255, 255, 0.7);
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 10px;
    font-family: 'Montserrat', sans-serif;
    font-weight: 500;
    font-size: 0.85rem;
    padding: 8px 16px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .treekipedia-tour-popover .tour-btn-back:hover {
    background: rgba(255, 255, 255, 0.1);
    color: #ffffff;
    border-color: rgba(255, 255, 255, 0.3);
  }

  /* ===== CLOSE BUTTON ===== */
  .treekipedia-tour-popover .tour-close-btn {
    position: absolute;
    top: 12px;
    right: 12px;
    background: none;
    border: none;
    color: rgba(255, 255, 255, 0.3);
    font-size: 22px;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.2s ease;
    line-height: 1;
  }

  .treekipedia-tour-popover .tour-close-btn:hover {
    color: rgba(255, 255, 255, 0.8);
    background: rgba(255, 255, 255, 0.08);
  }
`;
