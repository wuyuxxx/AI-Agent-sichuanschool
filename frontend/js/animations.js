/**
 * 智汇校园 — 动画系统 v2
 * 粒子网络 · 入场序列 · 滚动触发 · 消息动效
 */

gsap.registerPlugin(ScrollTrigger, ScrollToPlugin);

// ================================================================
// 粒子网络背景（明亮版）
// ================================================================
function initParticleNetwork() {
    const canvas = document.getElementById('particle-canvas');
    if (!canvas) return () => {};
    const ctx = canvas.getContext('2d');
    let particles = [], animId = null;

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }

    function createParticles(count = 80) {
        particles = [];
        for (let i = 0; i < count; i++) {
            particles.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                vx: (Math.random() - 0.5) * 0.2,
                vy: (Math.random() - 0.5) * 0.2,
                r: Math.random() * 2 + 0.5,
                alpha: Math.random() * 0.3 + 0.08,
                hue: Math.random() > 0.6 ? 210 : 260,
            });
        }
    }

    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        for (const p of particles) {
            p.x += p.vx; p.y += p.vy;
            if (p.x < -20) p.x = canvas.width + 20;
            if (p.x > canvas.width + 20) p.x = -20;
            if (p.y < -20) p.y = canvas.height + 20;
            if (p.y > canvas.height + 20) p.y = -20;

            // outer glow
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r * 2, 0, Math.PI * 2);
            ctx.fillStyle = `hsla(${p.hue}, 70%, 75%, 0.04)`;
            ctx.fill();

            // core
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = `hsla(${p.hue}, 70%, 75%, ${p.alpha})`;
            ctx.fill();
        }

        // connections
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 120) {
                    const alpha = 0.06 * (1 - dist / 120);
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `hsla(${particles[i].hue}, 60%, 80%, ${alpha})`;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        }

        animId = requestAnimationFrame(draw);
    }

    resize();
    createParticles();
    draw();

    window.addEventListener('resize', () => { resize(); createParticles(); });
    return () => cancelAnimationFrame(animId);
}

// ================================================================
// 滚动进度条
// ================================================================
function initScrollProgress() {
    const bar = document.getElementById('scroll-progress');
    if (!bar) return;

    gsap.to(bar, {
        scaleX: 1,
        ease: 'none',
        scrollTrigger: {
            trigger: document.body,
            start: 'top top',
            end: 'bottom bottom',
            scrub: 0.3,
        },
    });
}

// ================================================================
// Hero 入场序列
// ================================================================
function runHeroEntrance() {
    const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });

    tl.from('.hero__badge', {
        y: -20, opacity: 0, duration: 0.5,
    }, 0.15);

    tl.from('.hero__title-line', {
        y: 40, opacity: 0, duration: 0.7,
        stagger: 0.2,
    }, 0.3);

    tl.from('.hero__subtitle', {
        y: 20, opacity: 0, duration: 0.5,
    }, 0.7);

    tl.from('.hero__btn', {
        y: 20, opacity: 0, scale: 0.9, duration: 0.5,
        stagger: 0.1,
    }, 0.9);

    tl.from('.hero__indicator', {
        opacity: 0, y: -10, duration: 0.4,
    }, 1.3);
}

// ================================================================
// 滚动触发：导航栏变色
// ================================================================
function initNavbarScroll() {
    const navbar = document.getElementById('navbar');
    if (!navbar) return;

    ScrollTrigger.create({
        start: 'top -40',
        onUpdate: (self) => {
            if (self.progress > 0) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        },
    });
}

// ================================================================
// 滚动触发：对话区入场
// ================================================================
function initChatReveal() {
    const chatSection = document.getElementById('chat-section');
    if (!chatSection) return;

    // Set initial invisible state explicitly
    gsap.set('.chat-section__label', { opacity: 0, y: -15 });
    gsap.set('.chat-section__title', { opacity: 0, y: 20 });
    gsap.set('.chat-section__desc', { opacity: 0, y: 15 });
    gsap.set('.chat-container', { opacity: 0, y: 60, scale: 0.94 });
    gsap.set('.chat-header', { opacity: 0, y: -12 });
    gsap.set('.chat-input-area', { opacity: 0, y: 15 });

    let revealed = false;
    function animateChat() {
        if (revealed) return;
        revealed = true;

        const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });
        tl.to('.chat-section__label', { opacity: 1, y: 0, duration: 0.4 }, 0);
        tl.to('.chat-section__title', { opacity: 1, y: 0, duration: 0.5 }, 0.15);
        tl.to('.chat-section__desc', { opacity: 1, y: 0, duration: 0.4 }, 0.3);
        tl.to('.chat-container', { opacity: 1, y: 0, scale: 1, duration: 0.9, ease: 'back.out(1.3)' }, 0.35);
        tl.to('.chat-header', { opacity: 1, y: 0, duration: 0.3 }, 0.9);
        tl.to('.chat-input-area', { opacity: 1, y: 0, duration: 0.3 }, 0.95);
        tl.call(() => animateWelcomeMessage(), [], 1.0);
        tl.call(() => pulseSendButton(), [], 1.5);
    }

    // Primary: GSAP ScrollTrigger
    ScrollTrigger.create({
        trigger: chatSection,
        start: 'top 85%',
        once: true,
        onEnter: animateChat,
    });

    // Fallback: manual scroll check (ensures content visibility)
    const scrollCheck = () => {
        const rect = chatSection.getBoundingClientRect();
        if (rect.top < window.innerHeight * 0.88) {
            animateChat();
            window.removeEventListener('scroll', scrollCheck);
        }
    };
    window.addEventListener('scroll', scrollCheck, { passive: true });
    scrollCheck();
}

// ================================================================
// 滚动触发：技术栈卡片入场
// ================================================================
function initTechReveal() {
    const techSection = document.getElementById('tech-section');
    if (!techSection) return;

    // Set initial invisible state explicitly
    gsap.set('.tech-section__label', { opacity: 0, y: -15 });
    gsap.set('.tech-section__title', { opacity: 0, y: 20 });
    gsap.set('.tech-section__desc', { opacity: 0, y: 15 });
    gsap.set('.tech-card', { opacity: 0, y: 50, scale: 0.92 });

    let revealed = false;
    function animateTech() {
        if (revealed) return;
        revealed = true;

        const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });
        tl.to('.tech-section__label', { opacity: 1, y: 0, duration: 0.4 }, 0);
        tl.to('.tech-section__title', { opacity: 1, y: 0, duration: 0.5 }, 0.15);
        tl.to('.tech-section__desc', { opacity: 1, y: 0, duration: 0.4 }, 0.3);
        tl.to('.tech-card', { opacity: 1, y: 0, scale: 1, duration: 0.6, stagger: 0.12, ease: 'back.out(1.1)' }, 0.35);
    }

    // Primary: GSAP ScrollTrigger
    ScrollTrigger.create({
        trigger: techSection,
        start: 'top 85%',
        once: true,
        onEnter: animateTech,
    });

    // Fallback: manual scroll check (ensures content visibility)
    const scrollCheck = () => {
        const rect = techSection.getBoundingClientRect();
        if (rect.top < window.innerHeight * 0.88) {
            animateTech();
            window.removeEventListener('scroll', scrollCheck);
        }
    };
    window.addEventListener('scroll', scrollCheck, { passive: true });
    scrollCheck();
}

// ================================================================
// 欢迎消息动画（逐句显现）
// ================================================================
function animateWelcomeMessage() {
    const welcomeMsg = document.querySelector('#chat-messages .message.assistant');
    if (!welcomeMsg) return;

    gsap.set(welcomeMsg, { opacity: 1, y: 0 });

    const paragraphs = welcomeMsg.querySelectorAll('.msg-content p');
    if (paragraphs.length) {
        gsap.set(paragraphs, { opacity: 0, y: 6 });
        gsap.to(paragraphs, {
            opacity: 1, y: 0,
            duration: 0.45,
            stagger: 0.2,
            ease: 'power2.out',
            delay: 0.1,
        });
    }
}

// ================================================================
// 单条消息入场
// ================================================================
function animateMessageIn(element) {
    if (!element) return;
    gsap.fromTo(element,
        { opacity: 0, y: 16, scale: 0.97 },
        {
            opacity: 1, y: 0, scale: 1,
            duration: 0.4,
            ease: 'back.out(1.3)',
            clearProps: 'transform',
        }
    );
}

// ================================================================
// 打字指示器
// ================================================================
let typingTween = null;

function showTypingIndicator(container) {
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
    container.appendChild(indicator);

    const dots = indicator.querySelectorAll('.typing-dot');
    typingTween = gsap.fromTo(dots,
        { y: 0, opacity: 0.3 },
        {
            y: -5, opacity: 1,
            duration: 0.4,
            stagger: 0.1,
            repeat: -1,
            yoyo: true,
            ease: 'sine.inOut',
        }
    );

    return indicator;
}

function hideTypingIndicator(indicator) {
    if (typingTween) { typingTween.kill(); typingTween = null; }
    if (indicator && indicator.parentNode) {
        gsap.to(indicator, {
            opacity: 0, duration: 0.15,
            onComplete: () => indicator.remove(),
        });
    }
}

// ================================================================
// 滚动到底部（平滑）
// ================================================================
function smoothScrollToBottom() {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    gsap.to(container, {
        scrollTo: { y: container.scrollHeight, autoKill: false },
        duration: 0.3,
        ease: 'power2.out',
        overwrite: 'auto',
    });
}

// ================================================================
// 发送按钮脉冲引导
// ================================================================
function pulseSendButton() {
    const btn = document.getElementById('send-btn');
    if (!btn || btn.disabled) return;
    gsap.fromTo(btn,
        { boxShadow: '0 0 0 0 rgba(74, 143, 231, 0.25)' },
        {
            boxShadow: '0 0 0 16px rgba(74, 143, 231, 0)',
            duration: 0.8,
            ease: 'power2.out',
            delay: 0.3,
        }
    );
    gsap.delayedCall(2.5, () => {
        if (!btn.disabled) {
            gsap.fromTo(btn,
                { boxShadow: '0 0 0 0 rgba(74, 143, 231, 0.25)' },
                { boxShadow: '0 0 0 16px rgba(74, 143, 231, 0)', duration: 0.8, ease: 'power2.out' }
            );
        }
    });
}

// ================================================================
// Hero 滚动触发按钮
// ================================================================
function initHeroScrollButtons() {
    const startBtn = document.getElementById('hero-start-btn');
    const learnBtn = document.getElementById('hero-learn-btn');
    const chatSection = document.getElementById('chat-section');
    const techSection = document.getElementById('tech-section');

    if (startBtn && chatSection) {
        startBtn.addEventListener('click', () => {
            gsap.to(window, {
                scrollTo: { y: '#chat-section', offsetY: 20 },
                duration: 1,
                ease: 'power3.inOut',
            });
        });
    }

    if (learnBtn && techSection) {
        learnBtn.addEventListener('click', () => {
            gsap.to(window, {
                scrollTo: { y: '#tech-section', offsetY: 20 },
                duration: 1,
                ease: 'power3.inOut',
            });
        });
    }
}

// ================================================================
// 导航栏链接显示/隐藏
// ================================================================
function initNavReveal() {
    const nav = document.getElementById('navbar-nav');
    if (!nav) return;

    // 初始隐藏
    gsap.set(nav, { opacity: 0, y: -6, pointerEvents: 'none' });

    let navShown = false;

    function showNav() {
        if (navShown) return;
        navShown = true;
        gsap.to(nav, {
            opacity: 1, y: 0,
            duration: 0.5,
            ease: 'power3.out',
            onComplete: () => { nav.style.pointerEvents = 'auto'; },
        });
        // 首次显示时把下划线放到首页位置
        const firstLink = nav.querySelector('.nav-link');
        if (firstLink) moveUnderline(firstLink);
    }

    function hideNav() {
        if (!navShown) return;
        navShown = false;
        gsap.to(nav, {
            opacity: 0, y: -6,
            duration: 0.3,
            ease: 'power2.in',
            onComplete: () => { nav.style.pointerEvents = 'none'; },
        });
    }

    // 滚动到接近对话区时显示
    ScrollTrigger.create({
        trigger: '#chat-section',
        start: 'top 90%',
        end: 'top 60%',
        onEnter: showNav,
        onLeaveBack: hideNav,
    });
}

// ================================================================
// 导航栏活动下划线跟踪
// ================================================================
function moveUnderline(link) {
    const underline = document.getElementById('nav-underline');
    const nav = document.getElementById('navbar-nav');
    if (!underline || !link || !nav) return;

    const linkRect = link.getBoundingClientRect();
    const navRect = nav.getBoundingClientRect();

    gsap.to(underline, {
        x: linkRect.left - navRect.left,
        width: linkRect.width,
        duration: 0.45,
        ease: 'power3.out',
        overwrite: 'auto',
    });
}

function initNavTracking() {
    const links = document.querySelectorAll('.nav-link');
    if (!links.length) return;

    // 每个 section 对应一个 ScrollTrigger
    const sections = [
        { id: 'hero', link: 'hero' },
        { id: 'chat-section', link: 'chat' },
        { id: 'tech-section', link: 'tech' },
    ];

    let currentActive = '';

    sections.forEach(({ id, link }) => {
        const el = document.getElementById(id);
        if (!el) return;

        ScrollTrigger.create({
            trigger: el,
            start: 'top 35%',
            end: 'bottom 35%',
            onEnter: () => setActive(link),
            onEnterBack: () => setActive(link),
        });
    });

    function setActive(target) {
        if (target === currentActive) return;
        currentActive = target;

        // 更新 active class
        links.forEach(link => {
            link.classList.toggle('active', link.dataset.target === target);
        });

        // 移动下划线
        const activeLink = document.querySelector(`.nav-link[data-target="${target}"]`);
        if (activeLink) moveUnderline(activeLink);
    }
}

// ================================================================
// 导航链接点击滚动
// ================================================================
function initNavClickHandlers() {
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => {
            const target = link.dataset.target;
            const map = {
                hero: { selector: '#hero', offset: 0 },
                chat: { selector: '#chat-section', offset: 20 },
                tech: { selector: '#tech-section', offset: 20 },
            };
            const info = map[target];
            if (info) scrollToSection(info.selector, info.offset);
        });
    });
}

// ================================================================
// 平滑滚动（暴露给 main.js 使用）
// ================================================================
function scrollToSection(selector, offset) {
    gsap.to(window, {
        scrollTo: { y: selector, offsetY: offset || 0 },
        duration: 0.8,
        ease: 'power3.inOut',
    });
}

// ================================================================
// 初始化（合并）
// ================================================================
function initAnimations() {
    const cleanupParticles = initParticleNetwork();
    initScrollProgress();
    initNavbarScroll();
    initHeroScrollButtons();
    initNavReveal();
    initNavTracking();
    initNavClickHandlers();

    requestAnimationFrame(() => {
        runHeroEntrance();
        initChatReveal();
        initTechReveal();
    });

    // ScrollTrigger 刷新（确保在 DOM 完全加载后计算正确）
    requestAnimationFrame(() => {
        ScrollTrigger.refresh();
    });

    return cleanupParticles;
}
