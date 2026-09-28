import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function ProfileScreen() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login', { replace: true });
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const userName =
    user?.first_name && user?.last_name
      ? `${user.first_name} ${user.last_name}`
      : user?.username || 'User';
  const initial = user?.first_name?.charAt(0) || 'U';

  return (
    <div className="max-w-2xl mx-auto py-8">
      <div className="flex flex-col items-center pb-6 border-b border-border-1">
        <div className="w-20 h-20 rounded-full bg-bg-3 flex items-center justify-center mb-4">
          <span className="text-3xl font-bold text-primary-400">{initial}</span>
        </div>
        <div className="text-xl font-semibold text-fg-1">{userName}</div>
        <div className="text-sm text-fg-3 mt-1">{user?.email || 'No email'}</div>
      </div>

      <div className="mt-8">
        <button
          type="button"
          onClick={handleLogout}
          className="ck-btn ck-btn-danger w-full"
        >
          Log out
        </button>
      </div>

      <div className="text-center mt-8 text-2xs text-fg-4">Version 1.0.0</div>
    </div>
  );
}
