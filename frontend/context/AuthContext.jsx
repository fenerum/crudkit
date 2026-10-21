import { createContext, useContext, useEffect, useState } from 'react';
import CrudKitAPIClient from '../data/api';

// Default value keeps `useAuth()` destructurable even if a consumer renders
// outside the provider tree (notably during a Vite HMR transition while the
// provider module is reloading).
const AuthContext = createContext({
  user: null,
  loading: true,
  isAuthenticated: false,
  login: async (_username, _password) => {
    throw new Error('AuthProvider not mounted');
  },
  logout: async () => {},
});

const client = new CrudKitAPIClient();

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Always probe /api/v1/user/me/. SAML users authenticate via the Django
    // session cookie (DRF SessionAuthentication) and never have a JWT in
    // localStorage; an early-return on missing token would leave them as
    // user=null and bounce them back into /saml2/login/ in a loop.
    const checkAuthStatus = async () => {
      try {
        try {
          const userData = await client.httpGet('api/v1/user/me/').then((res) => res.json());
          setUser(userData);
        } catch (error) {
          if (error?.statusCode === 401 || error?.statusCode === 403) {
            console.log('Server rejected stored credentials, clearing tokens');
            client.clearTokens();
          } else {
            console.log('Auth check failed transiently; keeping tokens', error);
          }
        }
      } finally {
        setLoading(false);
      }
    };

    checkAuthStatus();
  }, []);

  const login = async (username, password) => {
    try {
      setLoading(true);
      const userData = await client.login(username, password);
      setUser(userData);
      return userData;
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    setLoading(true);
    await client.logout();
    setUser(null);
    setLoading(false);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        login,
        logout,
        loading,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
