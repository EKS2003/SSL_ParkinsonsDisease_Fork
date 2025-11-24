import {Navigate, Outlet, useLocation} from "react-router-dom";
import apiService from "@/services/api/api";

const RequireAuth = () => {
    const location = useLocation();

    if (!apiService.isAuthenticated()) {
        return <Navigate to="/login" state={{ from: location }} replace />;
    }

    return <Outlet />;
}

export default RequireAuth;