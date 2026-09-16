/**
 * auth_app.js
 * ===========
 * Modern Electricity Utility SaaS Authentication Portal
 * Pure Electricity & Energy Theme (Zero Leaves/Botanicals/Plants)
 * Full-screen single centered card layout with React 18
 */

const { useState, createElement: h } = React;

/* --- Minimal Modern Electricity & UI Icons --- */
function BoltLogoIcon() {
  return h(
    'svg',
    { width: 26, height: 26, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2.4, strokeLinecap: 'round', strokeLinejoin: 'round' },
    h('polygon', { points: '13 2 3 14 12 14 11 22 21 10 12 10 13 2' })
  );
}

function UserIcon() {
  return h(
    'svg',
    { width: 17, height: 17, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' },
    h('path', { d: 'M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2' }),
    h('circle', { cx: 12, cy: 7, r: 4 })
  );
}

function LockIcon() {
  return h(
    'svg',
    { width: 17, height: 17, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' },
    h('rect', { x: 3, y: 11, width: 18, height: 11, rx: 2, ry: 2 }),
    h('path', { d: 'M7 11V7a5 5 0 0 1 10 0v4' })
  );
}

function KeyIcon() {
  return h(
    'svg',
    { width: 17, height: 17, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' },
    h('circle', { cx: 7.5, cy: 15.5, r: 5.5 }),
    h('path', { d: 'm21 2-9.6 9.6' }),
    h('path', { d: 'm15.5 7.5 3 3L22 7l-3-3' })
  );
}

function EyeIcon({ open }) {
  if (open) {
    return h(
      'svg',
      { width: 17, height: 17, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' },
      h('path', { d: 'M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z' }),
      h('circle', { cx: 12, cy: 12, r: 3 })
    );
  }
  return h(
    'svg',
    { width: 17, height: 17, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' },
    h('path', { d: 'M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24' }),
    h('line', { x1: 1, y1: 1, x2: 23, y2: 23 })
  );
}

function ShieldCheckIcon() {
  return h(
    'svg',
    { width: 15, height: 15, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2.2, strokeLinecap: 'round', strokeLinejoin: 'round' },
    h('path', { d: 'M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z' }),
    h('path', { d: 'm9 12 2 2 4-4' })
  );
}

function ArrowRightIcon() {
  return h(
    'svg',
    { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2.3, strokeLinecap: 'round', strokeLinejoin: 'round' },
    h('line', { x1: 5, y1: 12, x2: 19, y2: 12 }),
    h('polyline', { points: '12 5 19 12 12 19' })
  );
}

function CheckIcon() {
  return h(
    'svg',
    { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2.2, strokeLinecap: 'round', strokeLinejoin: 'round' },
    h('polyline', { points: '20 6 9 17 4 12' })
  );
}

function AlertTriangleIcon() {
  return h(
    'svg',
    { width: 17, height: 17, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2.2, strokeLinecap: 'round', strokeLinejoin: 'round' },
    h('path', { d: 'm21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z' }),
    h('line', { x1: 12, y1: 9, x2: 12, y2: 13 }),
    h('line', { x1: 12, y1: 17, x2: 12.01, y2: 17 })
  );
}

function ZapOutlineIcon() {
  return h(
    'svg',
    { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' },
    h('polygon', { points: '13 2 3 14 12 14 11 22 21 10 12 10 13 2' })
  );
}

function CpuIcon() {
  return h(
    'svg',
    { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' },
    h('rect', { x: 4, y: 4, width: 16, height: 16, rx: 2 }),
    h('rect', { x: 9, y: 9, width: 6, height: 6 }),
    h('path', { d: 'M9 1v3 M15 1v3 M9 20v3 M15 20v3 M20 9h3 M20 14h3 M1 9h3 M1 14h3' })
  );
}

function FileTextIcon() {
  return h(
    'svg',
    { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' },
    h('path', { d: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z' }),
    h('polyline', { points: '14 2 14 8 20 8' })
  );
}

/* --- Pure Electricity Background (Transmission Towers + High Voltage Lines + Energy Waves) --- */
function ElectricityBackgroundCanvas() {
  return h(
    'svg',
    { className: 'bg-electricity-canvas', viewBox: '0 0 1440 900', fill: 'none', preserveAspectRatio: 'xMidYMid slice' },

    // Top subtle high-voltage power lines across the top
    h('path', {
      d: 'M0 120 Q 360 190, 720 140 T 1440 100',
      stroke: 'rgba(16, 185, 129, 0.12)',
      strokeWidth: 1.5,
      strokeDasharray: '6 4'
    }),
    h('path', {
      d: 'M0 150 Q 360 220, 720 170 T 1440 130',
      stroke: 'rgba(5, 150, 105, 0.08)',
      strokeWidth: 1.5
    }),

    // --- Transmission Tower 1 (Left - Large Architectural Power Tower Vector) ---
    // Main legs
    h('path', {
      d: 'M130 880 L180 340 L230 880',
      stroke: 'rgba(16, 185, 129, 0.28)',
      strokeWidth: 1.8,
      strokeLinecap: 'round'
    }),
    // Center spine & peak
    h('path', {
      d: 'M180 340 L180 290',
      stroke: 'rgba(16, 185, 129, 0.35)',
      strokeWidth: 2,
      strokeLinecap: 'round'
    }),
    // Crossarms & Insulator bars
    h('path', {
      d: 'M100 420 L260 420 M115 500 L245 500 M90 590 L270 590',
      stroke: 'rgba(16, 185, 129, 0.28)',
      strokeWidth: 1.6,
      strokeLinecap: 'round'
    }),
    // Cross braces (X-lattice engineering structure)
    h('path', {
      d: 'M155 420 L205 500 M205 420 L155 500 M145 500 L215 590 M215 500 L145 590 M135 590 L225 720 M225 590 L135 720 M130 720 L230 880 M230 720 L130 880',
      stroke: 'rgba(16, 185, 129, 0.18)',
      strokeWidth: 1.2
    }),
    // Insulators hanging from crossbars
    h('path', { d: 'M100 420 L100 440 M260 420 L260 440 M90 590 L90 610 M270 590 L270 610', stroke: 'rgba(5, 150, 105, 0.3)', strokeWidth: 2 }),

    // --- Transmission Tower 2 (Further Left - Secondary Substation Tower) ---
    h('path', {
      d: 'M40 880 L70 500 L100 880 M50 560 L90 560 M45 640 L95 640 M40 730 L100 730',
      stroke: 'rgba(16, 185, 129, 0.16)',
      strokeWidth: 1.3,
      strokeLinecap: 'round'
    }),
    h('path', { d: 'M70 500 L70 460', stroke: 'rgba(16, 185, 129, 0.2)', strokeWidth: 1.5 }),

    // High Voltage Lines from Left Towers towards Right across bottom
    h('path', {
      d: 'M100 440 C 260 620, 520 720, 920 680',
      stroke: 'rgba(16, 185, 129, 0.18)',
      strokeWidth: 1.5
    }),
    h('path', {
      d: 'M260 440 C 460 660, 780 760, 1200 690',
      stroke: 'rgba(5, 150, 105, 0.14)',
      strokeWidth: 1.5
    }),
    h('path', {
      d: 'M270 610 C 500 780, 900 820, 1440 730',
      stroke: 'rgba(16, 185, 129, 0.16)',
      strokeWidth: 1.5,
      strokeDasharray: '8 5'
    }),

    // --- Large Faint Watermark Lightning Bolt on Right Side ---
    h('path', {
      d: 'M1260 120 L1180 440 L1250 440 L1150 780 L1340 370 L1250 370 Z',
      fill: 'rgba(16, 185, 129, 0.045)',
      stroke: 'rgba(16, 185, 129, 0.12)',
      strokeWidth: 1.5,
      strokeLinejoin: 'round'
    }),

    // Smooth Electricity Energy Wave Ribbons at Bottom (Clean Vector Waves, NO Hills)
    h('path', {
      d: 'M0 810 Q 380 720, 740 790 T 1440 760 L 1440 900 L 0 900 Z',
      fill: 'url(#energyWaveGrad1)',
      opacity: 0.65
    }),
    h('path', {
      d: 'M0 845 C 420 780, 860 880, 1440 820 L 1440 900 L 0 900 Z',
      fill: 'url(#energyWaveGrad2)',
      opacity: 0.85
    }),

    // Energy Node Points
    h('circle', { cx: 180, cy: 290, r: 4, fill: 'rgba(16, 185, 129, 0.4)' }),
    h('circle', { cx: 100, cy: 440, r: 3, fill: 'rgba(16, 185, 129, 0.35)' }),
    h('circle', { cx: 260, cy: 440, r: 3, fill: 'rgba(16, 185, 129, 0.35)' }),

    // Gradient Definitions
    h(
      'defs',
      null,
      h(
        'linearGradient',
        { id: 'energyWaveGrad1', x1: '0%', y1: '0%', x2: '100%', y2: '0%' },
        h('stop', { offset: '0%', stopColor: '#10b981', stopOpacity: '0.1' }),
        h('stop', { offset: '50%', stopColor: '#059669', stopOpacity: '0.18' }),
        h('stop', { offset: '100%', stopColor: '#10b981', stopOpacity: '0.08' })
      ),
      h(
        'linearGradient',
        { id: 'energyWaveGrad2', x1: '0%', y1: '0%', x2: '100%', y2: '0%' },
        h('stop', { offset: '0%', stopColor: '#059669', stopOpacity: '0.12' }),
        h('stop', { offset: '100%', stopColor: '#047857', stopOpacity: '0.22' })
      )
    )
  );
}

/* --- Main Application Component --- */
function AuthApp() {
  const [view, setView] = useState('login'); // 'login' | 'forgot_pin' | 'forgot_new_pass'
  const [username, setUsername] = useState('Admin');
  const [password, setPassword] = useState('');
  const [pin, setPin] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [showPassword, setShowPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const switchView = (newView) => {
    setError('');
    setSuccess('');
    setView(newView);
  };

  // Handle Login Submission
  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!username.trim() || !password) {
      setError('Please enter both username and password.');
      return;
    }

    setLoading(true);
    try {
      const resp = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password })
      });
      const data = await resp.json();

      if (resp.ok && data.success) {
        window.location.href = '/';
      } else {
        setError(data.error || 'Invalid username or password.');
      }
    } catch (err) {
      setError('Unable to reach server. Please check your network connection.');
    } finally {
      setLoading(false);
    }
  };

  // Handle PIN verification
  const handleVerifyPin = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!pin.trim()) {
      setError('Please enter your 6-digit security PIN.');
      return;
    }

    setLoading(true);
    try {
      const resp = await fetch('/api/verify-pin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin: pin.trim() })
      });
      const data = await resp.json();

      if (resp.ok && data.success) {
        setView('forgot_new_pass');
        setError('');
      } else {
        setError(data.error || 'Invalid security PIN. Please enter the correct 6-digit PIN.');
      }
    } catch (err) {
      setError('Unable to reach server. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Handle Password Reset
  const handleResetPassword = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!newPassword) {
      setError('Please enter a new password.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match. Please re-enter.');
      return;
    }

    setLoading(true);
    try {
      const resp = await fetch('/api/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          pin: pin.trim(),
          new_password: newPassword,
          confirm_password: confirmPassword
        })
      });
      const data = await resp.json();

      if (resp.ok && data.success) {
        setPassword('');
        setNewPassword('');
        setConfirmPassword('');
        setPin('');
        setView('login');
        setSuccess('Password updated successfully! You can now log in with your new password.');
      } else {
        setError(data.error || 'Failed to update password.');
      }
    } catch (err) {
      setError('Unable to reach server. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Render Login Form
  const renderLoginForm = () => {
    return h(
      'form',
      { onSubmit: handleLogin, noValidate: false },
      h(
        'div',
        { className: 'form-field' },
        h('label', { className: 'field-label' }, 'Username'),
        h(
          'div',
          { className: 'input-container' },
          h('span', { className: 'field-icon' }, h(UserIcon)),
          h('input', {
            type: 'text',
            className: 'text-input',
            value: username,
            onChange: (e) => setUsername(e.target.value),
            placeholder: 'Enter username (e.g. Admin)',
            required: true,
            autoComplete: 'username'
          })
        )
      ),
      h(
        'div',
        { className: 'form-field' },
        h('label', { className: 'field-label' }, 'Password'),
        h(
          'div',
          { className: 'input-container' },
          h('span', { className: 'field-icon' }, h(LockIcon)),
          h('input', {
            type: showPassword ? 'text' : 'password',
            className: 'text-input',
            value: password,
            onChange: (e) => setPassword(e.target.value),
            placeholder: 'Enter password',
            required: true,
            autoComplete: 'current-password'
          }),
          h(
            'button',
            {
              type: 'button',
              className: 'input-icon-btn',
              onClick: () => setShowPassword(!showPassword),
              title: showPassword ? 'Hide password' : 'Show password',
              'aria-label': showPassword ? 'Hide password' : 'Show password'
            },
            h(EyeIcon, { open: showPassword })
          )
        )
      ),
      h(
        'div',
        { className: 'form-sublinks' },
        h(
          'button',
          {
            type: 'button',
            className: 'forgot-btn',
            onClick: () => switchView('forgot_pin')
          },
          'Forgot Password?'
        )
      ),
      h(
        'button',
        {
          type: 'submit',
          className: 'submit-btn',
          disabled: loading
        },
        loading
          ? [h('span', { className: 'btn-loader', key: 'spin' }), 'Signing In...']
          : [h(ArrowRightIcon, { key: 'arrow' }), 'Sign In']
      )
    );
  };

  // Render PIN Screen
  const renderForgotPinForm = () => {
    return h(
      'form',
      { onSubmit: handleVerifyPin },
      h(
        'div',
        { className: 'form-field' },
        h('label', { className: 'field-label' }, '6-Digit Security PIN'),
        h(
          'div',
          { className: 'input-container' },
          h('input', {
            type: 'text',
            className: 'text-input pin-code-input',
            maxLength: 6,
            value: pin,
            onChange: (e) => setPin(e.target.value.replace(/\D/g, '')),
            placeholder: '••••••',
            autoFocus: true,
            required: true
          })
        )
      ),
      h(
        'button',
        {
          type: 'submit',
          className: 'submit-btn',
          disabled: loading || pin.length < 6
        },
        loading ? [h('span', { className: 'btn-loader', key: 'spin' }), 'Verifying PIN...'] : 'Verify PIN'
      ),
      h(
        'button',
        {
          type: 'button',
          className: 'back-btn',
          onClick: () => switchView('login')
        },
        'Back to Sign In'
      )
    );
  };

  // Render New Password Form
  const renderNewPasswordForm = () => {
    return h(
      'form',
      { onSubmit: handleResetPassword },
      h(
        'div',
        { className: 'form-field' },
        h('label', { className: 'field-label' }, 'New Password'),
        h(
          'div',
          { className: 'input-container' },
          h('span', { className: 'field-icon' }, h(KeyIcon)),
          h('input', {
            type: showNewPassword ? 'text' : 'password',
            className: 'text-input',
            value: newPassword,
            onChange: (e) => setNewPassword(e.target.value),
            placeholder: 'Enter new password',
            required: true
          }),
          h(
            'button',
            {
              type: 'button',
              className: 'input-icon-btn',
              onClick: () => setShowNewPassword(!showNewPassword),
              title: showNewPassword ? 'Hide password' : 'Show password'
            },
            h(EyeIcon, { open: showNewPassword })
          )
        )
      ),
      h(
        'div',
        { className: 'form-field' },
        h('label', { className: 'field-label' }, 'Confirm Password'),
        h(
          'div',
          { className: 'input-container' },
          h('span', { className: 'field-icon' }, h(LockIcon)),
          h('input', {
            type: showConfirmPassword ? 'text' : 'password',
            className: 'text-input',
            value: confirmPassword,
            onChange: (e) => setConfirmPassword(e.target.value),
            placeholder: 'Confirm new password',
            required: true
          }),
          h(
            'button',
            {
              type: 'button',
              className: 'input-icon-btn',
              onClick: () => setShowConfirmPassword(!showConfirmPassword),
              title: showConfirmPassword ? 'Hide password' : 'Show password'
            },
            h(EyeIcon, { open: showConfirmPassword })
          )
        )
      ),
      h(
        'button',
        {
          type: 'submit',
          className: 'submit-btn',
          disabled: loading
        },
        loading ? [h('span', { className: 'btn-loader', key: 'spin' }), 'Saving Password...'] : 'Save New Password'
      ),
      h(
        'button',
        {
          type: 'button',
          className: 'back-btn',
          onClick: () => switchView('login')
        },
        'Cancel'
      )
    );
  };

  // Card view titles & subtitles
  let viewTitle = 'Utility Sign In';
  let viewSubtitle = 'Enter authorized credentials to access the billing system.';

  if (view === 'forgot_pin') {
    viewTitle = 'PIN Verification';
    viewSubtitle = 'Enter your 6-digit administrative PIN to reset password.';
  } else if (view === 'forgot_new_pass') {
    viewTitle = 'Set New Password';
    viewSubtitle = 'Enter and confirm a new secure password for Admin.';
  }

  return h(
    'div',
    { className: 'auth-page' },

    // Top Enterprise Bar (Desktop)
    h(
      'header',
      { className: 'utility-topbar', 'aria-hidden': 'true' },
      h('span', null, h('i', { className: 'status-live-dot' }), 'Power Grid: Operational'),
      h('span', { className: 'utility-topbar-sep' }, '|'),
      h('span', null, 'Smart Billing Engine'),
      h('span', { className: 'utility-topbar-sep' }, '|'),
      h('span', null, 'Secure Core v2.6')
    ),

    // Ambient Soft Green Glows
    h('div', { className: 'ambient-glow-left', 'aria-hidden': 'true' }),
    h('div', { className: 'ambient-glow-right', 'aria-hidden': 'true' }),

    // Electricity/Energy Canvas & Power Grid Background (Zero Leaves/Trees/Plants)
    h('div', { className: 'bg-energy-grid', 'aria-hidden': 'true' }),
    h(ElectricityBackgroundCanvas),

    // SaaS Technology Side Features (Desktop Only, Pure Tech / Electricity)
    h(
      'aside',
      { className: 'saas-features-aside', 'aria-hidden': 'true' },
      h(
        'div',
        { className: 'saas-feature-item' },
        h('div', { className: 'saas-feature-icon' }, h(ShieldCheckIcon)),
        h(
          'div',
          { className: 'saas-feature-text' },
          h('h4', null, 'Secure & Reliable'),
          h('p', null, 'Enterprise-grade static access controls & isolation.')
        )
      ),
      h(
        'div',
        { className: 'saas-feature-item' },
        h('div', { className: 'saas-feature-icon' }, h(FileTextIcon)),
        h(
          'div',
          { className: 'saas-feature-text' },
          h('h4', null, 'Fast & Accurate'),
          h('p', null, 'Sub-point exact currency & bar graph alignment.')
        )
      ),
      h(
        'div',
        { className: 'saas-feature-item' },
        h('div', { className: 'saas-feature-icon' }, h(ZapOutlineIcon)),
        h(
          'div',
          { className: 'saas-feature-text' },
          h('h4', null, 'Grid Engine'),
          h('p', null, 'Automated template detection & consumer mapping.')
        )
      )
    ),

    // Centered Login Card Container
    h(
      'main',
      { className: 'auth-container' },
      h(
        'div',
        { className: 'login-card' },

        // Top Branding in Card
        h(
          'div',
          { className: 'brand-header' },
          h('div', { className: 'logo-badge', 'aria-label': 'Electricity Bill Generator Logo' }, h(BoltLogoIcon)),
          h('h1', { className: 'brand-title' }, 'Electricity Bill Generator'),
          h('p', { className: 'brand-subtitle' }, 'Smart & Secure Electricity Billing System')
        ),

        // Divider with Centered Security Pill Badge
        h(
          'div',
          { className: 'card-divider-container' },
          h('div', { className: 'card-divider-line', 'aria-hidden': 'true' }),
          h(
            'div',
            { className: 'security-badge' },
            h(ShieldCheckIcon),
            h('span', null, 'Secure Authentication')
          )
        ),

        // View Header
        h(
          'div',
          { className: 'view-header' },
          h('h2', { className: 'view-title' }, viewTitle),
          h('p', { className: 'view-subtitle' }, viewSubtitle)
        ),

        // Error Banner
        error &&
          h(
            'div',
            { className: 'alert-box error', role: 'alert' },
            h(AlertTriangleIcon),
            h('span', null, error)
          ),

        // Success Banner
        success &&
          h(
            'div',
            { className: 'alert-box success', role: 'status' },
            h(CheckIcon),
            h('span', null, success)
          ),

        // Active Form View
        view === 'login' && renderLoginForm(),
        view === 'forgot_pin' && renderForgotPinForm(),
        view === 'forgot_new_pass' && renderNewPasswordForm(),

        // Bottom Security/Access Message
        h(
          'div',
          { className: 'card-footer' },
          h(ShieldCheckIcon),
          h('span', null, 'Protected by static access controls. Authorized utility staff only.')
        )
      )
    )
  );
}

// Mount the React Application
const rootElement = document.getElementById('root');
if (rootElement) {
  const root = ReactDOM.createRoot(rootElement);
  root.render(h(AuthApp));
}
