import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { appConfig } from '../../utils/appConfig';

export default function LoginScreen() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();
  const { login, loading } = useAuth();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) {
      setError('Username and password are required');
      return;
    }
    setError('');

    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch (err) {
      console.error('Login error:', err);
      setError('Invalid username or password');
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-bg-0 px-5">
      <h1 className="text-3xl font-semibold tracking-tight text-fg-1 mb-2">{appConfig.app_name}</h1>
      <p className="text-sm text-fg-3 mb-7">Sign in to continue</p>

      <form onSubmit={handleLogin} className="w-full max-w-[360px] flex flex-col gap-3">
        {error && (
          <div className="text-danger text-xs text-center" role="alert">
            {error}
          </div>
        )}

        <input
          type="text"
          placeholder="Username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoCapitalize="off"
          autoComplete="username"
          className="ck-input"
        />

        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          className="ck-input"
        />

        <button type="submit" disabled={loading} className="ck-btn ck-btn-primary w-full">
          {loading ? 'Logging in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}
