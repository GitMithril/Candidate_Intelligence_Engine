import { initializeApp } from "firebase/app"
import {
  getAuth,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  GoogleAuthProvider,
  signOut as firebaseSignOut,
  onAuthStateChanged,
  type User,
} from "firebase/auth"

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: "candidate-intelligence-engine.firebaseapp.com",
  projectId: "candidate-intelligence-engine",
  storageBucket: "candidate-intelligence-engine.firebasestorage.app",
  messagingSenderId: "833605822326",
  appId: "1:833605822326:web:d4a570f29fb5df1f113c57",
  measurementId: "G-JNZXQLKQ16",
}

const app = initializeApp(firebaseConfig)
export const auth = getAuth(app)

const googleProvider = new GoogleAuthProvider()

export const signInWithGoogle = () => signInWithPopup(auth, googleProvider)

export const signInWithEmail = (email: string, password: string) =>
  signInWithEmailAndPassword(auth, email, password)

export const signUpWithEmail = (email: string, password: string) =>
  createUserWithEmailAndPassword(auth, email, password)

export const signOut = async () => {
  // Clear chat session from localStorage on logout
  localStorage.removeItem("cie_chat_session")
  localStorage.removeItem("cie_chat_messages")
  await firebaseSignOut(auth)
}

export const getIdToken = async (): Promise<string | null> => {
  const user = auth.currentUser
  return user ? user.getIdToken() : null
}

export { onAuthStateChanged, type User }
