document.addEventListener('DOMContentLoaded', () => {
  // Слайдер баннер
  const slides = document.querySelectorAll('.hero-slide');
  const dots = document.querySelectorAll('.hero-dot');

  if (slides.length && dots.length) {
    let currentIndex = 0;

    function goToSlide(index) {
      slides[currentIndex].classList.remove('hero-slide-active');
      dots[currentIndex].classList.remove('dot-active');

      currentIndex = index;

      slides[currentIndex].classList.add('hero-slide-active');
      dots[currentIndex].classList.add('dot-active');
    }

    dots.forEach((dot, index) => {
      dot.addEventListener('click', () => goToSlide(index));
    });
  }

  // Модальное окно с полным описанием
  const roleCards = document.querySelectorAll('[data-role-card]');
  const modalBackdrop = document.getElementById('role-modal');
  const modalTitle = document.getElementById('role-modal-title');
  const modalText = document.getElementById('role-modal-text');
  const modalClose = document.getElementById('role-modal-close');

  if (modalBackdrop && modalTitle && modalText) {
    const openModal = (title, html) => {
      modalTitle.textContent = title;
      modalText.innerHTML = html;
      modalBackdrop.classList.add('role-modal-backdrop-open');
      document.body.style.overflow = 'hidden';
    };

    const closeModal = () => {
      modalBackdrop.classList.remove('role-modal-backdrop-open');
      document.body.style.overflow = '';
    };

    // Клик по крестику
    if (modalClose) {
      modalClose.addEventListener('click', closeModal);
    }

    // Клик по фону вокруг модалки
    modalBackdrop.addEventListener('click', (event) => {
      if (event.target === modalBackdrop) {
        closeModal();
      }
    });

    // Escape — закрыть
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        closeModal();
      }
    });

    // Клик по карточке — открыть модалку
    roleCards.forEach((card) => {
      card.addEventListener('click', () => {
        const titleEl = card.querySelector('.role-card-title');
        const fullEl = card.querySelector('.role-card-full');

        const title = titleEl ? titleEl.textContent.trim() : '';
        const html = fullEl ? fullEl.innerHTML : '';

        openModal(title, html);
      });
    });
  }
  // Модальное окно для режимов игры
  const modeCards = document.querySelectorAll('[data-mode-card]');
  const modeBackdrop = document.getElementById('mode-modal');
  const modeTitle = document.getElementById('mode-modal-title');
  const modeText = document.getElementById('mode-modal-text');
  const modeClose = document.getElementById('mode-modal-close');

  if (modeBackdrop && modeTitle && modeText) {
    const openModeModal = (title, html) => {
      modeTitle.textContent = title;
      modeText.innerHTML = html;
      modeBackdrop.classList.add('role-modal-backdrop-open');
      document.body.style.overflow = 'hidden';
    };

    const closeModeModal = () => {
      modeBackdrop.classList.remove('role-modal-backdrop-open');
      document.body.style.overflow = '';
    };

    if (modeClose) {
      modeClose.addEventListener('click', closeModeModal);
    }

    modeBackdrop.addEventListener('click', (event) => {
      if (event.target === modeBackdrop) {
        closeModeModal();
      }
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        closeModeModal();
      }
    });

    modeCards.forEach((card) => {
      card.addEventListener('click', () => {
        const titleEl = card.querySelector('.mode-card-title');
        const fullEl = card.querySelector('.mode-card-full');

        const title = titleEl ? titleEl.textContent.trim() : '';
        const html = fullEl ? fullEl.innerHTML : '';

        openModeModal(title, html);
      });
    });
  }
});
