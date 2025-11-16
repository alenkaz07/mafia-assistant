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

  // Модальное окно с полным описанием ролей
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

  // Сортировка таблицы
  const setupSortableTables = () => {
    const tables = document.querySelectorAll('.sessions-table');

    tables.forEach((table) => {
      const headers = table.querySelectorAll('thead th');

      headers.forEach((th, colIndex) => {
        const sortType = th.dataset.sortType;
        if (!sortType) return;

        th.classList.add('sortable-header');

        th.addEventListener('click', () => {
          const tbody = table.tBodies[0];
          if (!tbody) return;

          const currentDir =
            th.dataset.sortDir === 'asc'
              ? 'asc'
              : th.dataset.sortDir === 'desc'
              ? 'desc'
              : null;

          const newDir = currentDir === 'asc' ? 'desc' : 'asc';

          // сбрасываем состояние остальных заголовков
          headers.forEach((h) => {
            h.dataset.sortDir = '';
            h.classList.remove('sorted-asc', 'sorted-desc');
          });

          th.dataset.sortDir = newDir;
          th.classList.add(newDir === 'asc' ? 'sorted-asc' : 'sorted-desc');

          const rows = Array.from(tbody.querySelectorAll('tr'));

          const getCellValue = (row) => {
            const cell = row.children[colIndex];
            if (!cell) return '';
            if (cell.dataset.sortValue !== undefined) {
              return cell.dataset.sortValue;
            }
            return cell.textContent.trim();
          };

          rows.sort((rowA, rowB) => {
            let a = getCellValue(rowA);
            let b = getCellValue(rowB);

            if (sortType === 'number') {
              a = parseFloat(a.replace(',', '.')) || 0;
              b = parseFloat(b.replace(',', '.')) || 0;
            } else {
              a = a.toLowerCase();
              b = b.toLowerCase();
            }

            if (a < b) return newDir === 'asc' ? -1 : 1;
            if (a > b) return newDir === 'asc' ? 1 : -1;
            return 0;
          });

          rows.forEach((row) => tbody.appendChild(row));
        });
      });
    });
  };

  // Таймер дня (1,5 минуты на обсуждение)
  const dayTimerButton = document.getElementById('day-timer-start');
  const dayTimerDisplay = document.getElementById('day-timer-display');

  if (dayTimerButton && dayTimerDisplay) {
    let timerId = null;

    const formatTime = (seconds) => {
      const m = String(Math.floor(seconds / 60)).padStart(2, '0');
      const s = String(seconds % 60).padStart(2, '0');
      return `${m}:${s}`;
    };

    const startTimer = (duration) => {
      let remaining = duration;
      dayTimerDisplay.textContent = formatTime(remaining);

      if (timerId) {
        clearInterval(timerId);
      }

      dayTimerDisplay.classList.remove('timer-finished');

      timerId = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
          clearInterval(timerId);
          timerId = null;
          dayTimerDisplay.textContent = '00:00';
          dayTimerDisplay.classList.add('timer-finished');
          return;
        }
        dayTimerDisplay.textContent = formatTime(remaining);
      }, 1000);
    };

    dayTimerButton.addEventListener('click', () => {
      startTimer(90); // 1,5 минуты
    });
  }

  setupSortableTables();
});
