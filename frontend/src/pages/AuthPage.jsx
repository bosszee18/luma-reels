import { SignIn, SignUp } from "@clerk/react";
import { Prism } from "@/components/Prism";

export default function AuthPage({ mode = "in" }) {
  return (
    <div className="grain min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:flex flex-col justify-between p-12 border-r border-[#F3D9A2]/10 relative overflow-hidden">
        <p className="font-serif text-2xl">Luma <em className="text-[#F3D9A2]">Atelier</em></p>
        <div className="flex justify-center"><Prism size={1.2} /></div>
        <div>
          <p className="tag">Studio sinematik AI</p>
          <h1 className="mt-3 text-5xl font-serif tracking-tight leading-tight">AutoClip, AutoMotion,<br />dan Explainer — dalam satu atelier.</h1>
        </div>
      </div>
      <div className="flex flex-col items-center justify-center p-6 gap-6">
        <p className="lg:hidden font-serif text-3xl">Luma <em className="text-[#F3D9A2]">Atelier</em></p>
        {mode === "in" ? <SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" withSignUp />
          : <SignUp routing="path" path="/sign-up" signInUrl="/sign-in" />}
      </div>
    </div>
  );
}
