export const validateEmail = (email) => {
    return String(email)
        .toLowerCase()
        .endsWith("@gmail.com");
};

// 2. Check for min length 8
export const validatePassword = (password) => {
    return password.length >= 8;
};

/** * MOCK DATABASE LOGIC (LocalStorage)
 * This handles the "storage" part of your request.
 */

// Save a new user to the local list
export const saveUserToDB = (email, password) => {
    try {
        const users = JSON.parse(localStorage.getItem("users") || "[]");

        // Safety check: Does this email already exist?
        const userExists = users.find(u => u.email.toLowerCase() === email.toLowerCase());

        if (userExists) {
            return { success: false, message: "This email is already registered." };
        }

        // Add new user
        users.push({ email, password });
        localStorage.setItem("users", JSON.stringify(users));
        return { success: true };
    } catch (error) {
        return { success: false, message: "Database error. Please try again." };
    }
};

// Check credentials during Login
export const checkUserCredentials = (email, password) => {
    try {
        const users = JSON.parse(localStorage.getItem("users") || "[]");
        // Find a user where both email AND password match
        const user = users.find(
            u => u.email.toLowerCase() === email.toLowerCase() && u.password === password
        );
        return !!user; // Returns true if user exists, false otherwise
    } catch (error) {
        return false;
    }
};