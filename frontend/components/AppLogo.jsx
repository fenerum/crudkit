import { appConfig } from "../utils/appConfig";
import defaultLogoUrl from "../images/logo.svg";

export default function AppLogo() {
  return (
    <img
      src={appConfig.logo_url || defaultLogoUrl}
      alt={appConfig.app_name}
      style={{width: 24, height: 24, borderRadius: 6, flex: '0 0 24px', objectFit: 'contain'}}
    />
  );
}
