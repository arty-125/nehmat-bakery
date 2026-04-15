/**
 * Nehmat Bakery — Public JavaScript
 * Handles: header scroll • mobile nav • hero slider • scroll reveal
 */

'use strict';

// ── Header scroll behaviour ───────────────────────────────────────────────────
(function initHeader() {
  const header = document.querySelector('.site-header');
  if (!header) return;

  const onScroll = () => {
    header.classList.toggle('scrolled', window.scrollY > 20);
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
})();

// ── Mobile navigation ─────────────────────────────────────────────────────────
(function initMobileNav() {
  const hamburger = document.querySelector('.hamburger');
  const navList   = document.querySelector('.nav-list');
  if (!hamburger || !navList) return;

  hamburger.addEventListener('click', () => {
    const open = hamburger.classList.toggle('open');
    navList.classList.toggle('open', open);
    hamburger.setAttribute('aria-expanded', String(open));
    document.body.style.overflow = open ? 'hidden' : '';
  });

  // Close nav when a link is clicked
  navList.querySelectorAll('a').forEach(a => {
    a.addEventListener('click', () => {
      hamburger.classList.remove('open');
      navList.classList.remove('open');
      document.body.style.overflow = '';
    });
  });

  // Close on outside click
  document.addEventListener('click', e => {
    if (!hamburger.contains(e.target) && !navList.contains(e.target)) {
      hamburger.classList.remove('open');
      navList.classList.remove('open');
      document.body.style.overflow = '';
    }
  });
})();

// ── Active nav link ───────────────────────────────────────────────────────────
(function setActiveNav() {
  const path  = window.location.pathname;
  const links = document.querySelectorAll('.nav-list a');
  links.forEach(a => {
    const href = a.getAttribute('href');
    const isActive = href === path || (href !== '/' && path.startsWith(href));
    a.classList.toggle('active', isActive);
  });
})();

// ── Hero Slider ───────────────────────────────────────────────────────────────
class HeroSlider {
  constructor(root) {
    this.root     = root;
    this.track    = root.querySelector('.slides-track');
    this.slides   = Array.from(root.querySelectorAll('.slide'));
    this.dots     = Array.from(root.querySelectorAll('.slider-dot'));
    this.prevBtn  = root.querySelector('.slider-arrow.prev');
    this.nextBtn  = root.querySelector('.slider-arrow.next');

    this.count    = this.slides.length;
    this.current  = 0;
    this.timer    = null;
    this.interval = 5500; // ms
    this.dragging = false;
    this.dragStartX = 0;

    if (this.count === 0) return;
    this._goto(0, false);
    this._bindEvents();
    this._startAuto();
  }

  _goto(index, animate = true) {
    if (!animate) {
      this.track.style.transition = 'none';
    } else {
      this.track.style.transition = '';
    }

    this.slides[this.current]?.classList.remove('active');
    this.dots[this.current]?.classList.remove('active');

    this.current = (index + this.count) % this.count;

    this.track.style.transform = `translateX(-${this.current * 100}%)`;
    this.slides[this.current].classList.add('active');
    this.dots[this.current]?.classList.add('active');

    // Pause/play videos
    this.slides.forEach((slide, i) => {
      const video = slide.querySelector('video');
      if (!video) return;
      if (i === this.current) {
        video.play().catch(() => {});
      } else {
        video.pause();
        video.currentTime = 0;
      }
    });
  }

  next() { this._goto(this.current + 1); }
  prev() { this._goto(this.current - 1); }

  _startAuto() {
    this._stopAuto();
    this.timer = setInterval(() => this.next(), this.interval);
  }
  _stopAuto() { clearInterval(this.timer); }

  _bindEvents() {
    this.prevBtn?.addEventListener('click', () => { this._stopAuto(); this.prev(); this._startAuto(); });
    this.nextBtn?.addEventListener('click', () => { this._stopAuto(); this.next(); this._startAuto(); });

    this.dots.forEach((dot, i) => {
      dot.addEventListener('click', () => { this._stopAuto(); this._goto(i); this._startAuto(); });
    });

    // Pause on hover
    this.root.addEventListener('mouseenter', () => this._stopAuto());
    this.root.addEventListener('mouseleave', () => this._startAuto());

    // Touch / swipe
    this.root.addEventListener('touchstart', e => {
      this.dragStartX = e.touches[0].clientX;
      this.dragging = true;
    }, { passive: true });
    this.root.addEventListener('touchmove', e => {
      if (!this.dragging) return;
      // prevent vertical scroll stealing only on significant horizontal drag
      const dx = Math.abs(e.touches[0].clientX - this.dragStartX);
      if (dx > 10) e.preventDefault();
    }, { passive: false });
    this.root.addEventListener('touchend', e => {
      if (!this.dragging) return;
      this.dragging = false;
      const dx = e.changedTouches[0].clientX - this.dragStartX;
      if (Math.abs(dx) > 48) {
        this._stopAuto();
        dx < 0 ? this.next() : this.prev();
        this._startAuto();
      }
    });

    // Keyboard
    document.addEventListener('keydown', e => {
      if (e.key === 'ArrowLeft')  { this._stopAuto(); this.prev(); this._startAuto(); }
      if (e.key === 'ArrowRight') { this._stopAuto(); this.next(); this._startAuto(); }
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const sliderEl = document.querySelector('.hero');
  if (sliderEl) new HeroSlider(sliderEl);
});

// ── Scroll-reveal ─────────────────────────────────────────────────────────────
(function initReveal() {
  const options = { threshold: 0.12, rootMargin: '0px 0px -40px 0px' };
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
        observer.unobserve(entry.target);
      }
    });
  }, options);

  document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
})();

// ── Flash auto-dismiss ────────────────────────────────────────────────────────
(function initFlash() {
  const msgs = document.querySelectorAll('.flash');
  msgs.forEach(msg => {
    setTimeout(() => {
      msg.style.transition = 'opacity .4s, transform .4s';
      msg.style.opacity = '0';
      msg.style.transform = 'translateY(-8px)';
      setTimeout(() => msg.remove(), 420);
    }, 4000);
  });
})();
