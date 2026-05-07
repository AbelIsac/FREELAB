// Particles effect
function createParticles() {
    const particlesContainer = document.querySelector('.particles');
    
    for (let i = 0; i < 50; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particle.style.left = Math.random() * 100 + '%';
        particle.style.animationDuration = (Math.random() * 20 + 10) + 's';
        particle.style.animationDelay = Math.random() * 5 + 's';
        particle.style.width = particle.style.height = (Math.random() * 4 + 1) + 'px';
        particlesContainer.appendChild(particle);
    }
}

// Header scroll effect
function handleScroll() {
    const header = document.querySelector('.header');
    if (window.scrollY > 100) {
        document.body.classList.add('scrolled');
    } else {
        document.body.classList.remove('scrolled');
    }
}

// Flash messages auto close
function initFlashMessages() {
    const closeButtons = document.querySelectorAll('.flash-close');
    closeButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.target.closest('.flash-message').style.animation = 'slideInRight 0.3s ease reverse';
            setTimeout(() => {
                e.target.closest('.flash-message').remove();
            }, 300);
        });
    });

    // Auto remove after 5 seconds
    setTimeout(() => {
        document.querySelectorAll('.flash-message').forEach(msg => {
            msg.style.animation = 'slideInRight 0.3s ease reverse';
            setTimeout(() => msg.remove(), 300);
        });
    }, 5000);
}

// Smooth scrolling for anchor links
function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
}

// Intersection Observer for animations
function initAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    });

    document.querySelectorAll('.producto-card, .section-title').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(50px)';
        el.style.transition = 'all 0.6s ease';
        observer.observe(el);
    });
}

// Newsletter form
function initNewsletter() {
    const forms = document.querySelectorAll('.newsletter-form');
    forms.forEach(form => {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            const input = form.querySelector('input');
            input.value = '¡Gracias por suscribirte! 🎉';
            input.style.background = '#10b981';
            setTimeout(() => {
                input.value = '';
                input.style.background = '';
            }, 3000);
        });
    });
}

// Initialize everything
document.addEventListener('DOMContentLoaded', () => {
    createParticles();
    initFlashMessages();
    initSmoothScroll();
    initAnimations();
    initNewsletter();
    
    window.addEventListener('scroll', handleScroll);
});

// Mobile menu toggle
document.querySelector('.hamburger')?.addEventListener('click', () => {
    document.querySelector('.nav-menu').classList.toggle('active');

    
});
