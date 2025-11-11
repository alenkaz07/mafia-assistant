document.addEventListener('DOMContentLoaded', () => {
  const slides = document.querySelectorAll('.hero-slide');
  const dots = document.querySelectorAll('.hero-dot');

  if (!slides.length || !dots.length) return;

  let currentIndex = 0;

  function goToSlide(index) {
    // снять активность со старого слайда и точки
    slides[currentIndex].classList.remove('hero-slide-active');
    dots[currentIndex].classList.remove('dot-active');

    currentIndex = index;

    // включить новый
    slides[currentIndex].classList.add('hero-slide-active');
    dots[currentIndex].classList.add('dot-active');
  }

  dots.forEach((dot, index) => {
    dot.addEventListener('click', () => goToSlide(index));
  });
});
