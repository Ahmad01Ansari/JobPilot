"use client";

import React, { useMemo, useRef, useState, useEffect, Component, ErrorInfo, ReactNode } from "react";
import Image from "next/image";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";
import { motion, useScroll, useTransform, AnimatePresence } from "framer-motion";
import { Download, Github, Terminal, Sparkles, ShieldCheck, Send, MessageSquare, Bot, User, CornerDownLeft, Zap, CheckCircle2 } from "lucide-react";

// Robust WebGL availability detection
function checkWebGLSupport(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2") || canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
    return Boolean(gl);
  } catch (e) {
    return false;
  }
}

// Robust Error Boundary
interface ErrorBoundaryProps {
  children: ReactNode;
  fallback: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

class RobotErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(_: Error): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.warn("3D WebGL fallback activated:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

class HeartCurve extends THREE.Curve<THREE.Vector3> {
  constructor() {
    super();
  }
  getPoint(t: number, optionalTarget = new THREE.Vector3()) {
    t = t * Math.PI * 2;
    const x = 16 * Math.pow(Math.sin(t), 3);
    const y =
      13 * Math.cos(t) -
      5 * Math.cos(2 * t) -
      2 * Math.cos(3 * t) -
      Math.cos(4 * t);

    return optionalTarget.set(x * 0.002, (y + 6) * 0.002, 0);
  }
}

const sharedHeartCurve = new HeartCurve();

function ResponsiveGroup({
  children,
  scale = 1,
}: {
  children: React.ReactNode;
  scale?: number;
}) {
  const { viewport } = useThree();
  const s = Math.min(1.1, viewport.width / 3.5) * scale;
  return <group scale={s}>{children}</group>;
}

function GlassCapsule({
  color,
  power,
  intensity,
}: {
  color: string;
  power: number;
  intensity: number;
}) {
  const materialRef = useRef<THREE.ShaderMaterial>(null);

  const uniforms = useMemo(
    () => ({
      color: { value: new THREE.Color("#ffffff") },
      power: { value: 2.5 },
      intensity: { value: 0.6 },
    }),
    [],
  );

  useFrame(() => {
    if (materialRef.current) {
      materialRef.current.uniforms.color.value.set(color);
      materialRef.current.uniforms.power.value = power;
      materialRef.current.uniforms.intensity.value = intensity;
    }
  });

  return (
    <mesh>
      <sphereGeometry args={[0.3, 32, 32, 0, Math.PI * 2, 0, Math.PI]} />
      <shaderMaterial
        ref={materialRef}
        uniforms={uniforms}
        vertexShader={`
          varying vec3 vNormal;
          varying vec3 vViewPosition;
          void main() {
            vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
            vViewPosition = -mvPosition.xyz;
            vNormal = normalize(normalMatrix * normal);
            gl_Position = projectionMatrix * mvPosition;
          }
        `}
        fragmentShader={`
          uniform vec3 color;
          uniform float power;
          uniform float intensity;
          varying vec3 vNormal;
          varying vec3 vViewPosition;
          void main() {
            vec3 normal = normalize(vNormal);
            vec3 viewDir = normalize(vViewPosition);
            float fresnel = 1.0 - max(dot(viewDir, normal), 0.0);
            fresnel = pow(fresnel, power);
            gl_FragColor = vec4(color, fresnel * intensity);
          }
        `}
        transparent={true}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </mesh>
  );
}

const earBaseMat = new THREE.MeshStandardMaterial({
  color: "#334155",
  roughness: 0.5,
});
const earRingMat = new THREE.MeshStandardMaterial({
  color: "#64748b",
  roughness: 0.3,
});
const earCenterMat = new THREE.MeshStandardMaterial({
  color: "#1e293b",
  roughness: 0.8,
});
const antennaBaseMat = new THREE.MeshStandardMaterial({
  color: "#475569",
  roughness: 0.4,
  metalness: 0.5,
});
const antennaStickMat = new THREE.MeshStandardMaterial({
  color: "#94a3b8",
  roughness: 0.4,
  metalness: 0.2,
});

function RobotEar({
  position,
  scale = 1,
  isLeft = false,
  tipColor = "#ff7a00",
}: {
  position: [number, number, number];
  scale?: number;
  isLeft?: boolean;
  tipColor?: string;
}) {
  const dir = isLeft ? -1 : 1;
  const tipMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: tipColor,
        roughness: 0.2,
        toneMapped: false,
      }),
    [tipColor],
  );

  return (
    <group position={position} scale={scale}>
      <mesh
        rotation={[0, 0, Math.PI / 2]}
        castShadow
        receiveShadow
        material={earBaseMat}
      >
        <cylinderGeometry args={[0.04, 0.04, 0.025, 24]} />
      </mesh>

      <mesh
        position={[dir * 0.012, 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
        receiveShadow
        material={earRingMat}
      >
        <torusGeometry args={[0.032, 0.008, 16, 24]} />
      </mesh>

      <mesh
        position={[dir * 0.012, 0, 0]}
        rotation={[0, 0, Math.PI / 2]}
        castShadow
        receiveShadow
        material={earCenterMat}
      >
        <cylinderGeometry args={[0.03, 0.03, 0.005, 24]} />
      </mesh>

      <group position={[dir * 0.015, 0.035, 0]} rotation={[-0.4, 0, 0]}>
        <mesh
          position={[0, 0.01, 0]}
          castShadow
          receiveShadow
          material={antennaBaseMat}
        >
          <cylinderGeometry args={[0.006, 0.008, 0.02, 12]} />
        </mesh>
        <mesh
          position={[0, 0.06, 0]}
          castShadow
          receiveShadow
          material={antennaStickMat}
        >
          <cylinderGeometry args={[0.003, 0.003, 0.1, 8]} />
        </mesh>
        <mesh
          position={[0, 0.11, 0]}
          castShadow
          receiveShadow
          material={tipMat}
        >
          <sphereGeometry args={[0.006, 12, 12]} />
        </mesh>
      </group>
    </group>
  );
}

const eyeMat = new THREE.MeshBasicMaterial({
  color: new THREE.Color(2, 2, 2),
  toneMapped: false,
  transparent: true,
});
const heartMat = new THREE.MeshBasicMaterial({
  color: "#ff3366",
  toneMapped: false,
});

function RobotEye({
  position,
  rotation,
  scale = 1,
  blinkDuration = 0.15,
  blinkCycle = 3.0,
  isLovedRef,
}: {
  position: [number, number, number];
  rotation: [number, number, number];
  scale?: number;
  blinkDuration?: number;
  blinkCycle?: number;
  isLovedRef: React.MutableRefObject<boolean>;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const normalEyesRef = useRef<THREE.Group>(null);
  const heartEyeRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (!groupRef.current || !normalEyesRef.current || !heartEyeRef.current)
      return;

    const isHeart = isLovedRef.current;
    normalEyesRef.current.visible = !isHeart;
    heartEyeRef.current.visible = isHeart;

    const elapsedTime = state.clock ? state.clock.getElapsedTime() : performance.now() / 1000;
    const cycle = elapsedTime % blinkCycle;

    let targetScaleY = 1;
    if (cycle < blinkDuration && !isHeart) {
      const progress = cycle / blinkDuration;
      const blinkClose = Math.sin(progress * Math.PI);
      targetScaleY = Math.max(0.05, 1.0 - blinkClose);
    }

    groupRef.current.scale.set(scale, scale * targetScaleY, scale);
  });

  const { topPath, bottomPath } = useMemo(() => {
    const w = 0.025;
    const h = 0.035;
    const r = 0.02;
    const g = 0.005;

    const tPath = new THREE.CurvePath<THREE.Vector3>();
    tPath.add(new THREE.LineCurve3(new THREE.Vector3(-w, g, 0), new THREE.Vector3(-w, h - r, 0)));
    tPath.add(new THREE.QuadraticBezierCurve3(new THREE.Vector3(-w, h - r, 0), new THREE.Vector3(-w, h, 0), new THREE.Vector3(-w + r, h, 0)));
    tPath.add(new THREE.LineCurve3(new THREE.Vector3(-w + r, h, 0), new THREE.Vector3(w - r, h, 0)));
    tPath.add(new THREE.QuadraticBezierCurve3(new THREE.Vector3(w - r, h, 0), new THREE.Vector3(w, h, 0), new THREE.Vector3(w, h - r, 0)));
    tPath.add(new THREE.LineCurve3(new THREE.Vector3(w, h - r, 0), new THREE.Vector3(w, g, 0)));

    const bPath = new THREE.CurvePath<THREE.Vector3>();
    bPath.add(new THREE.LineCurve3(new THREE.Vector3(-w, -g, 0), new THREE.Vector3(-w, -(h - r), 0)));
    bPath.add(new THREE.QuadraticBezierCurve3(new THREE.Vector3(-w, -(h - r), 0), new THREE.Vector3(-w, -h, 0), new THREE.Vector3(-w + r, -h, 0)));
    bPath.add(new THREE.LineCurve3(new THREE.Vector3(-w + r, -h, 0), new THREE.Vector3(w - r, -h, 0)));
    bPath.add(new THREE.QuadraticBezierCurve3(new THREE.Vector3(w - r, -h, 0), new THREE.Vector3(w, -h, 0), new THREE.Vector3(w, -(h - r), 0)));
    bPath.add(new THREE.LineCurve3(new THREE.Vector3(w, -(h - r), 0), new THREE.Vector3(w, -g, 0)));

    return { topPath: tPath, bottomPath: bPath };
  }, []);

  return (
    <group ref={groupRef} position={position} rotation={rotation} scale={scale}>
      <mesh ref={heartEyeRef} visible={false} material={heartMat}>
        <tubeGeometry args={[sharedHeartCurve, 48, 0.0035, 6, true]} />
      </mesh>

      <group ref={normalEyesRef}>
        <mesh material={eyeMat}>
          <tubeGeometry args={[topPath, 16, 0.0035, 6, false]} />
        </mesh>
        <mesh material={eyeMat}>
          <tubeGeometry args={[bottomPath, 16, 0.0035, 6, false]} />
        </mesh>
      </group>
    </group>
  );
}

export function RobotPrototype({
  position = [0, -0.3, 0],
  neckParams = {
    baseR: 0.25,
    baseH: -0.01,
    midR: 0.23,
    midH: 0.02,
    lipBottomR: 0.27,
    lipBottomH: 0.025,
    lipTopR: 0.28,
    lipTopH: 0.05,
    innerR: 0.24,
    innerDropH: 0.03,
  },
  bodyParams = { bodyBevelR: 0.21, bodyBevelY: 0.38, bodyBevelT: 0.015 },
  color = "#1e293b",
  pantallaColor = "#ff7a00",
  pantallaBrillo = 1.4,
  blinkCycle = 3.0,
  metalness = 0.2,
  antennaColor = "#ff7a00",
  onRobotClick,
  targetOffset = 0,
}: {
  position?: [number, number, number];
  neckParams?: Record<string, number>;
  bodyParams?: Record<string, number>;
  color?: string;
  pantallaColor?: string;
  pantallaBrillo?: number;
  blinkCycle?: number;
  metalness?: number;
  antennaColor?: string;
  onRobotClick?: () => void;
  targetOffset?: number;
}) {
  const isLovedRef = useRef(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const bodyRef = useRef<THREE.Group>(null);
  const headRef = useRef<THREE.Group>(null);

  const design = {
    pantallaColor: pantallaColor,
    pantallaGrosor: 3.8,
    pantallaBrillo: pantallaBrillo,
    separacionOjos: 0.07,
    tamañoOrejas: 1.3,
    escalaOjos: 1.1,
    parpadeoFrecuencia: blinkCycle,
    parpadeoDuracion: 0.45,
    colorChasis: color,
    alturaCabeza: 0.6,
  };

  const config = {
    moveSpeed: 0.35,
    bodyRotSpeed: 8.0,
    headRotSpeed: 16.0,
    bodyTiltX: 0.0,
    bodyTiltY: 0.75,
    headLookX: 0.3,
    headLookY: 1.6,
  };

  useFrame((state, delta) => {
    if (!bodyRef.current || !headRef.current) return;

    const dt = Math.min(delta, 0.1);
    const tx = state.pointer.x;
    const ty = state.pointer.y;

    const maxMoveX = state.viewport.width / 4.0;
    const targetPosX = position[0] + (tx + targetOffset) * maxMoveX * 0.3;
    bodyRef.current.position.x = THREE.MathUtils.lerp(
      bodyRef.current.position.x,
      targetPosX,
      config.moveSpeed * dt,
    );

    const relativeX = tx - (bodyRef.current.position.x - position[0]) / 2.5;
    const bodyTargetRotY = -relativeX * config.bodyTiltY;
    const bodyTargetRotX = relativeX * relativeX * config.bodyTiltX - ty * 0.2;
    const bodyTargetRotZ = -relativeX * 0.1;

    bodyRef.current.rotation.y = THREE.MathUtils.lerp(bodyRef.current.rotation.y, bodyTargetRotY, config.bodyRotSpeed * dt);
    bodyRef.current.rotation.x = THREE.MathUtils.lerp(bodyRef.current.rotation.x, bodyTargetRotX, config.bodyRotSpeed * dt);
    bodyRef.current.rotation.z = THREE.MathUtils.lerp(bodyRef.current.rotation.z, bodyTargetRotZ, config.bodyRotSpeed * dt);

    const headTargetRotY = relativeX * config.headLookY;
    const headTargetRotX = -ty * config.headLookX;

    headRef.current.rotation.y = THREE.MathUtils.lerp(headRef.current.rotation.y, headTargetRotY, config.headRotSpeed * dt);
    headRef.current.rotation.x = THREE.MathUtils.lerp(headRef.current.rotation.x, headTargetRotX, config.headRotSpeed * dt);
  });

  const handlePointerDown = (e: any) => {
    e.stopPropagation();
    isLovedRef.current = true;
    if (onRobotClick) onRobotClick();
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      isLovedRef.current = false;
    }, 2400);
  };

  const neckProfile = useMemo(() => {
    const points = [];
    points.push(new THREE.Vector2(neckParams.innerR, neckParams.baseH));
    points.push(new THREE.Vector2(neckParams.baseR, neckParams.baseH));
    points.push(new THREE.Vector2(neckParams.midR, neckParams.midH));
    points.push(new THREE.Vector2(neckParams.lipBottomR, neckParams.lipBottomH));
    points.push(new THREE.Vector2(neckParams.lipTopR, neckParams.lipTopH));
    points.push(new THREE.Vector2(neckParams.innerR, neckParams.lipTopH));
    points.push(new THREE.Vector2(neckParams.innerR, neckParams.lipTopH - neckParams.innerDropH));
    return points;
  }, [neckParams]);

  const chasisMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: design.colorChasis,
        roughness: 0.4,
        metalness: metalness,
      }),
    [design.colorChasis, metalness],
  );

  const headMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#0a0f1d",
        roughness: 0.7,
        metalness: 0.3,
      }),
    [],
  );

  return (
    <group
      ref={bodyRef}
      position={position}
      onPointerDown={handlePointerDown}
      onPointerOver={() => {
        if (typeof document !== "undefined") document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        if (typeof document !== "undefined") document.body.style.cursor = "auto";
      }}
    >
      <mesh castShadow receiveShadow material={chasisMat}>
        <sphereGeometry args={[0.43, 36, 36, 0, Math.PI * 2, Math.PI * 0.15, Math.PI * 0.85]} />
      </mesh>

      {bodyParams.bodyBevelT > 0 && (
        <mesh
          position={[0, bodyParams.bodyBevelY, 0]}
          rotation={[Math.PI / 2, 0, 0]}
          castShadow
          receiveShadow
          material={chasisMat}
        >
          <torusGeometry args={[bodyParams.bodyBevelR, bodyParams.bodyBevelT, 24, 36]} />
        </mesh>
      )}

      <mesh position={[0, 0.38, 0]} receiveShadow castShadow material={chasisMat}>
        <latheGeometry args={[neckProfile, 36]} />
      </mesh>

      <group ref={headRef} position={[0, design.alturaCabeza, 0]}>
        <mesh material={headMat} castShadow receiveShadow>
          <sphereGeometry args={[0.28, 36, 36, 0, Math.PI * 2, 0, Math.PI]} />
        </mesh>

        <GlassCapsule
          color={design.pantallaColor}
          power={design.pantallaGrosor}
          intensity={design.pantallaBrillo}
        />

        <group position={[0, -0.02, 0.29]}>
          <RobotEye
            position={[-design.separacionOjos, 0, 0]}
            rotation={[0, -0.2, 0]}
            scale={design.escalaOjos}
            blinkDuration={design.parpadeoDuracion}
            blinkCycle={design.parpadeoFrecuencia}
            isLovedRef={isLovedRef}
          />
          <RobotEye
            position={[design.separacionOjos, 0, 0]}
            rotation={[0, 0.2, 0]}
            scale={design.escalaOjos}
            blinkDuration={design.parpadeoDuracion}
            blinkCycle={design.parpadeoFrecuencia}
            isLovedRef={isLovedRef}
          />
        </group>

        <RobotEar
          position={[-0.29, 0, 0]}
          isLeft={true}
          scale={design.tamañoOrejas}
          tipColor={antennaColor}
        />
        <RobotEar
          position={[0.29, 0, 0]}
          isLeft={false}
          scale={design.tamañoOrejas}
          tipColor={antennaColor}
        />
      </group>
    </group>
  );
}

// High-Fidelity Spherical Robot Avatar (100% Visual Parity with 3D Three.js Model across all browsers)
export function AnimatedRobotSvg({
  color = "#ff7a00",
  name = "Root-01",
  status = "Portal Navigator",
  isThinking = false,
  onClick,
}: {
  color?: string;
  name?: string;
  status?: string;
  isThinking?: boolean;
  onClick?: () => void;
}) {
  const [blink, setBlink] = useState(false);
  const [loved, setLoved] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => {
      setBlink(true);
      setTimeout(() => setBlink(false), 200);
    }, 3200);
    return () => clearInterval(timer);
  }, []);

  const handleClick = () => {
    setLoved(true);
    if (onClick) onClick();
    setTimeout(() => setLoved(false), 2200);
  };

  const isOrange = color.includes("ff7a00") || color.includes("orange");
  const uniqueId = name.replace(/[^a-zA-Z0-9]/g, "");

  return (
    <motion.div
      onClick={handleClick}
      className="group relative flex flex-col items-center cursor-pointer select-none transition-transform hover:scale-105 active:scale-95"
      title={`Click ${name} to interact`}
      initial={{ y: 0 }}
      animate={{ y: [0, -8, 0] }}
      transition={{ repeat: Infinity, duration: 4.2, ease: "easeInOut" }}
    >
      <div className="relative w-48 h-56 sm:w-56 sm:h-64 flex items-center justify-center">
        <svg
          viewBox="0 0 200 240"
          className="w-full h-full overflow-visible drop-shadow-2xl"
        >
          <defs>
            {/* Soft Radial Ground Shadow Filter */}
            <filter id={`shadowFilter-${uniqueId}`} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="5" />
            </filter>

            {/* Spherical Ceramic Chassis Gradient */}
            <radialGradient id={`chassisGrad-${uniqueId}`} cx="35%" cy="30%" r="68%">
              <stop offset="0%" stopColor="#ffffff" />
              <stop offset="40%" stopColor={isOrange ? "#f8fafc" : "#f1f5f9"} />
              <stop offset="78%" stopColor="#cbd5e1" />
              <stop offset="100%" stopColor="#94a3b8" />
            </radialGradient>

            {/* Obsidian Glass Dome Head Gradient */}
            <radialGradient id={`headGrad-${uniqueId}`} cx="40%" cy="32%" r="64%">
              <stop offset="0%" stopColor="#334155" />
              <stop offset="45%" stopColor="#1e293b" />
              <stop offset="85%" stopColor="#090d16" />
              <stop offset="100%" stopColor="#020617" />
            </radialGradient>

            {/* Visor Capsule Inner Radial Glow */}
            <radialGradient id={`visorGlow-${uniqueId}`} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor={color} stopOpacity="0.35" />
              <stop offset="80%" stopColor={color} stopOpacity="0.08" />
              <stop offset="100%" stopColor="#000000" stopOpacity="0.95" />
            </radialGradient>

            {/* Metallic Collar Ring Gradient */}
            <linearGradient id={`collarGrad-${uniqueId}`} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#475569" />
              <stop offset="50%" stopColor="#94a3b8" />
              <stop offset="100%" stopColor="#334155" />
            </linearGradient>
          </defs>

          {/* 1. Ground Contact Shadow Disc */}
          <ellipse
            cx="100"
            cy="226"
            rx="56"
            ry="11"
            fill="#000000"
            opacity="0.45"
            filter={`url(#shadowFilter-${uniqueId})`}
          />

          {/* 2. Round Spherical Ceramic Body (Exact Three.js Sphere Geometry Parity) */}
          <circle
            cx="100"
            cy="164"
            r="52"
            fill={`url(#chassisGrad-${uniqueId})`}
          />

          {/* Specular Light Arc on Ceramic Torso */}
          <path
            d="M74,136 A46,46 0 0,1 126,136"
            fill="none"
            stroke="#ffffff"
            strokeWidth="3.5"
            strokeLinecap="round"
            opacity="0.75"
          />
          <ellipse
            cx="80"
            cy="145"
            rx="16"
            ry="9"
            fill="#ffffff"
            opacity="0.5"
            transform="rotate(-28 80 145)"
          />

          {/* Center Autonomous Core LED Badge */}
          <circle cx="100" cy="168" r="4.5" fill={color} opacity="0.9" style={{ filter: `drop-shadow(0 0 6px ${color})` }} />
          <circle cx="100" cy="168" r="8" fill="none" stroke={color} strokeWidth="1" opacity="0.4" />

          {/* 3. Lathe Neck Ring / Torus Collar */}
          <path
            d="M74,116 Q100,123 126,116 L124,122 Q100,129 76,122 Z"
            fill={`url(#collarGrad-${uniqueId})`}
            stroke="#1e293b"
            strokeWidth="1"
          />
          <ellipse cx="100" cy="118" rx="25" ry="5" fill="#64748b" />

          {/* 4. Smooth Dome Head */}
          <ellipse
            cx="100"
            cy="88"
            rx="36"
            ry="33"
            fill={`url(#headGrad-${uniqueId})`}
            stroke="#0f172a"
            strokeWidth="1.2"
          />

          {/* 5. Curved Glass Visor (Capsule Screen with Colored Neon Glow) */}
          <ellipse
            cx="100"
            cy="89"
            rx="31"
            ry="25"
            fill={`url(#visorGlow-${uniqueId})`}
            stroke={color}
            strokeWidth="2.4"
            style={{ filter: `drop-shadow(0 0 10px ${color})` }}
          />

          {/* Visor Specular Reflection Curve */}
          <path
            d="M78,79 Q100,68 122,79"
            fill="none"
            stroke="#ffffff"
            strokeWidth="2"
            strokeLinecap="round"
            opacity="0.45"
          />

          {/* 6. Expressive Glowing Eyes */}
          {loved ? (
            <g transform="translate(76, 78)">
              {/* Left Eye Heart Shape (Zero Emojis in Source) */}
              <path
                d="M8 14.5l-1-0.9C3.6 10.4 1.3 8.3 1.3 5.7 1.3 3.6 2.9 2 5 2c1.2 0 2.3 0.6 3 1.4C8.7 2.6 9.8 2 11 2c2.1 0 3.7 1.6 3.7 3.7 0 2.6-2.3 4.7-5.7 7.9L8 14.5z"
                fill="#ff3366"
                style={{ filter: `drop-shadow(0 0 6px #ff3366)` }}
              />
              {/* Right Eye Heart Shape */}
              <path
                d="M26 14.5l-1-0.9c-3.4-3.2-5.7-5.3-5.7-7.9 0-2.1 1.6-3.7 3.7-3.7 1.2 0 2.3 0.6 3 1.4 0.7-0.8 1.8-1.4 3-1.4 2.1 0 3.7 1.6 3.7 3.7 0 2.6-2.3 4.7-5.7 7.9L26 14.5z"
                fill="#ff3366"
                style={{ filter: `drop-shadow(0 0 6px #ff3366)` }}
              />
            </g>
          ) : (
            <g
              style={{
                transformOrigin: "100px 89px",
                transform: blink ? "scaleY(0.1)" : "scaleY(1)",
                transition: "transform 0.15s ease",
              }}
            >
              {/* Left Eye */}
              <rect
                x="88"
                y="81"
                width="6.5"
                height="16"
                rx="3.2"
                fill="#ffffff"
                style={{ filter: `drop-shadow(0 0 6px ${color})` }}
              />
              {/* Right Eye */}
              <rect
                x="106"
                y="81"
                width="6.5"
                height="16"
                rx="3.2"
                fill="#ffffff"
                style={{ filter: `drop-shadow(0 0 6px ${color})` }}
              />
            </g>
          )}

          {/* 7. Side Ears & Directional Antennas */}
          {/* Left Ear */}
          <ellipse cx="63" cy="89" rx="3.5" ry="9" fill="#334155" stroke="#475569" strokeWidth="1" />
          <ellipse cx="61" cy="89" rx="2" ry="7" fill="#64748b" />
          {/* Left Antenna Stick & Glowing Tip */}
          <line x1="61" y1="83" x2="51" y2="58" stroke="#94a3b8" strokeWidth="2.2" strokeLinecap="round" />
          <circle
            cx="51"
            cy="58"
            r="4.5"
            fill={color}
            style={{ filter: `drop-shadow(0 0 8px ${color})` }}
          />

          {/* Right Ear */}
          <ellipse cx="137" cy="89" rx="3.5" ry="9" fill="#334155" stroke="#475569" strokeWidth="1" />
          <ellipse cx="139" cy="89" rx="2" ry="7" fill="#64748b" />
          {/* Right Antenna Stick & Glowing Tip */}
          <line x1="139" y1="83" x2="149" y2="58" stroke="#94a3b8" strokeWidth="2.2" strokeLinecap="round" />
          <circle
            cx="149"
            cy="58"
            r="4.5"
            fill={color}
            style={{ filter: `drop-shadow(0 0 8px ${color})` }}
          />
        </svg>
      </div>

      {/* Nameplate & Status Badge */}
      <div className="mt-1 flex flex-col items-center">
        <span className="font-mono text-xs font-bold text-white tracking-wide">{name}</span>
        <span
          className="text-[10px] font-mono px-2.5 py-0.5 rounded-full mt-0.5"
          style={{
            backgroundColor: `${color}15`,
            color: color,
            border: `1px solid ${color}40`,
          }}
        >
          {status}
        </span>
      </div>
    </motion.div>
  );
}

export interface NavItem {
  label: string;
  href: string;
  target?: string;
}

export function AntennaNavbar({
  leftItems = [
    { label: "Demos", href: "#automation-demos" },
    { label: "Features", href: "#workflow" },
    { label: "Cockpit", href: "#showcase" },
    { label: "Platforms", href: "#platforms" },
    { label: "Architecture", href: "#architecture" },
  ],
  githubHref = "https://github.com/Ahmad01Ansari/JobPilot",
  downloadHref = "https://github.com/Ahmad01Ansari/JobPilot/releases",
}: {
  leftItems?: NavItem[];
  githubHref?: string;
  downloadHref?: string;
}) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const { scrollY } = useScroll();
  const lineOpacity = useTransform(scrollY, [0, 80], [1, 0.2]);

  return (
    <nav className="sticky top-0 z-50 w-full pt-2.5 sm:pt-4 px-3 sm:px-6 lg:px-8 pointer-events-none">
      <div className="w-full max-w-[1560px] mx-auto flex flex-col relative pointer-events-auto">
        
        {/* Main Navbar Bar */}
        <div className="flex items-center justify-between relative w-full gap-2 sm:gap-4">
          
          {/* Brand Lockup (Always Accessible on Left) */}
          <div className="flex items-center gap-2 sm:gap-4 z-20 shrink-0">
            <a href="#" className="flex items-center gap-2.5 sm:gap-3 group shrink-0 py-1" title="JobPilot Autonomous Career Engine">
              {/* Mascot Icon Container - Prominent, High-Contrast Titanium Robot */}
              <div className="relative w-11 h-11 sm:w-12 sm:h-12 rounded-xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-950 border border-slate-700/90 p-1 flex items-center justify-center shadow-[0_0_20px_rgba(255,122,0,0.22)] group-hover:border-orange-safety group-hover:shadow-[0_0_28px_rgba(255,122,0,0.45)] transition-all backdrop-blur-md">
                <Image
                  src="/brand/jobpilot-symbol-dark.svg"
                  alt="JobPilot Autonomous Agent Mascot"
                  width={40}
                  height={40}
                  className="w-9 h-9 sm:w-10 sm:h-10 object-contain drop-shadow-[0_2px_8px_rgba(0,0,0,0.8)] group-hover:scale-105 transition-transform"
                  priority
                />
              </div>

              {/* Typography Brand Lockup */}
              <div className="flex flex-col items-start justify-center">
                <div className="flex items-center gap-1.5">
                  <span className="font-sans text-lg sm:text-xl font-black tracking-tight text-white leading-none">
                    Job<span className="text-orange-safety">Pilot</span>
                  </span>
                  <span className="hidden sm:inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[9px] font-mono font-bold tracking-wider uppercase bg-orange-500/10 text-orange-400 border border-orange-500/30 shadow-[0_0_8px_rgba(255,122,0,0.15)]">
                    <span className="w-1.5 h-1.5 rounded-full bg-orange-safety animate-pulse" />
                    v0.1.0-beta
                  </span>
                </div>
                <span className="text-[10px] sm:text-[11px] font-mono font-medium text-slate-400 tracking-wide uppercase leading-tight mt-0.5 group-hover:text-slate-300 transition-colors">
                  Autonomous Cockpit
                </span>
              </div>
            </a>
          </div>

          {/* Desktop Navigation Pill Tabs (Centered & perfectly spaced) */}
          <div className="hidden lg:flex items-center gap-1.5 sm:gap-2 z-20">
            {leftItems.map((item, idx) => (
              <a
                key={item.label}
                href={item.href}
                target={item.target}
                rel={item.target === "_blank" ? "noopener noreferrer" : undefined}
                onMouseEnter={() => setHoveredIndex(idx)}
                onMouseLeave={() => setHoveredIndex(null)}
                className="relative px-3.5 py-1.5 rounded-full bg-slate-900/90 text-slate-200 hover:text-white border border-slate-700/80 hover:border-orange-safety/80 text-xs sm:text-sm font-semibold transition-all overflow-hidden shadow-lg backdrop-blur-md"
              >
                {item.label}
                {hoveredIndex === idx && (
                  <motion.div
                    layoutId="navbar-indicator-left"
                    className="absolute inset-0 border-b-[2px] border-orange-safety"
                    transition={{ type: "spring", stiffness: 400, damping: 30 }}
                  />
                )}
              </a>
            ))}
          </div>

          {/* Right Action Buttons */}
          <div className="flex items-center gap-2 sm:gap-3 z-20 shrink-0">
            <a
              href={githubHref}
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 sm:px-4 sm:py-2 rounded-full bg-slate-900/90 text-slate-300 hover:text-white border border-slate-700 hover:border-slate-500 text-xs sm:text-sm font-semibold transition-all shadow-md backdrop-blur-md flex items-center gap-1.5"
              title="GitHub Repository"
            >
              <Github className="h-4 w-4" />
              <span className="hidden sm:inline">GitHub</span>
            </a>
            <a
              href={downloadHref}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 sm:px-5 py-2 rounded-full bg-orange-safety text-white text-xs sm:text-sm font-black hover:bg-orange-600 transition-colors flex items-center gap-1.5 shadow-[0_0_20px_rgba(255,122,0,0.35)] shrink-0"
            >
              <Download className="h-4 w-4" />
              <span className="hidden xs:inline sm:inline">Download Beta</span>
              <span className="inline xs:hidden sm:hidden">Beta</span>
            </a>
          </div>
        </div>

        {/* Mobile & Tablet Horizontal Scrollable Pill Rail (< lg) */}
        <div className="flex lg:hidden items-center gap-1.5 overflow-x-auto no-scrollbar py-2 mt-2 w-full touch-pan-x -mx-1 px-1">
          {leftItems.map((item) => (
            <a
              key={item.label}
              href={item.href}
              target={item.target}
              rel={item.target === "_blank" ? "noopener noreferrer" : undefined}
              className="px-3 py-1 rounded-full bg-slate-900/95 text-slate-200 hover:text-white border border-slate-700/80 hover:border-orange-safety text-xs font-semibold whitespace-nowrap shrink-0 shadow-sm"
            >
              {item.label}
            </a>
          ))}
        </div>

        {/* Dynamic Dotted Divider */}
        <motion.div
          style={{ opacity: lineOpacity }}
          className="w-full mt-2 sm:mt-3.5 border-b border-dotted border-slate-700/60"
        />
      </div>
    </nav>
  );
}

// User-Facing Interactive Communication Knowledge Base
const PRESET_QUERIES = [
  {
    q: "How do you apply on Greenhouse & Lever?",
    bot: "Root-01",
    botRole: "Portal Navigator",
    botColor: "#ff7a00",
    answer: "I resolve nested dynamic iframes, classify applicant inputs semantically without hardcoded IDs, and inject your master profile coordinates. I then signal Kernel-02 to attach your resume and resolve custom screening questions.",
  },
  {
    q: "How does 5-Tier Q&A eliminate hallucinations?",
    bot: "Kernel-02",
    botRole: "5-Tier Q&A Engine",
    botColor: "#00ffc6",
    answer: "Strict provenance cascade! Tier 1 draws from Profile Facts, Tier 2 from Resume Facts, Tier 3 applies deterministic Q&A Rules, and Tier 4 evaluates confidence. If confidence is below 85%, Tier 5 pauses for mandatory human approval. Zero hallucinated facts.",
  },
  {
    q: "What happens during a Human Checkpoint?",
    bot: "Root-01",
    botRole: "Portal Navigator",
    botColor: "#ff7a00",
    answer: "Whenever salary expectations, custom essay prompts, or Cloudflare/hCaptcha appear, automation safely freezes and alerts you in the desktop cockpit. Once you confirm, we resume automatically.",
  },
  {
    q: "Where is my data and credentials stored?",
    bot: "Kernel-02",
    botRole: "5-Tier Q&A Engine",
    botColor: "#00ffc6",
    answer: "100% locally! All application history, resume variants, and SHA-256 submission proofs stay in your local SQLite vault (~/.jobpilot). Zero cloud telemetry and zero external server tracking.",
  },
];

export function RobotHero() {
  const [mounted, setMounted] = useState(false);
  const [hasWebGL, setHasWebGL] = useState(false);
  const [viewMode, setViewMode] = useState<"auto" | "3d" | "vector">("auto");
  const [chatHistory, setChatHistory] = useState([
    {
      sender: "Root-01",
      role: "Portal Navigator",
      color: "#ff7a00",
      text: "Greetings Candidate! I'm Root-01. I detect ATS portals and coordinate safe application traversals.",
    },
    {
      sender: "Kernel-02",
      role: "5-Tier Q&A Engine",
      color: "#00ffc6",
      text: "And I'm Kernel-02. I ensure zero hallucination across screening questions and commit SHA-256 audit proof to your local vault. Ask us anything below!",
    },
  ]);
  const [userInput, setUserInput] = useState("");
  const [isBotResponding, setIsBotResponding] = useState(false);

  useEffect(() => {
    setMounted(true);
    setHasWebGL(checkWebGLSupport());
  }, []);

  const handleSendPrompt = (questionText: string) => {
    if (!questionText.trim() || isBotResponding) return;

    // Add user message
    const newChat = [...chatHistory, { sender: "You", role: "Candidate", color: "#f8fafc", text: questionText }];
    setChatHistory(newChat);
    setUserInput("");
    setIsBotResponding(true);

    // Find matching preset or dynamic response
    setTimeout(() => {
      const match = PRESET_QUERIES.find(
        (p) => p.q.toLowerCase() === questionText.toLowerCase()
      );

      if (match) {
        setChatHistory((prev) => [
          ...prev,
          {
            sender: match.bot,
            role: match.botRole,
            color: match.botColor,
            text: match.answer,
          },
        ]);
      } else {
        // Dynamic autonomous answer
        setChatHistory((prev) => [
          ...prev,
          {
            sender: "Root-01",
            role: "Portal Navigator",
            color: "#ff7a00",
            text: `Analyzing target scope "${questionText}"... Scanning Greenhouse, Lever, Workday, Foundit, and Naukri. Automated filters set with humanized jitter delays.`,
          },
          {
            sender: "Kernel-02",
            role: "5-Tier Q&A Engine",
            color: "#00ffc6",
            text: `Verified candidate qualifications for "${questionText}". Matching resume variant primed. Ready to dispatch from your local desktop cockpit!`,
          },
        ]);
      }
      setIsBotResponding(false);
    }, 600);
  };

  return (
    <section className="relative w-full overflow-hidden bg-slate-950/70 backdrop-blur-[1px] text-slate-100 flex flex-col justify-between pt-2 pb-16 border-b border-slate-800/80">
      
      {/* Subtle Architectural Grid Accents (Edge-to-Edge Parity, Zero Slop Blobs) */}
      <div className="absolute inset-0 pointer-events-none opacity-[0.03] bg-[radial-gradient(#ffffff_1px,transparent_1px)] [background-size:24px_24px]" />

      {/* Top Antenna Navbar */}
      <AntennaNavbar />

      {/* Main Hero Cockpit: Asymmetric Split Grid Layout (Eliminates Left & Right Empty Sketch) */}
      <div className="relative z-20 mx-auto w-full max-w-[1560px] px-4 sm:px-8 lg:px-12 mt-6 lg:mt-10 flex-1 flex flex-col justify-between">
        
        {/* 2-Column Edge-to-Edge Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-10 items-stretch">
          
          {/* Left Column (7 cols): Command & Live Communicator */}
          <div className="lg:col-span-7 flex flex-col justify-between space-y-6">
            
            {/* System Context Pill */}
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/90 px-3.5 py-1 text-xs font-mono text-slate-300 w-fit backdrop-blur-md">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              <span>Local-first desktop agent • Linux &amp; Windows</span>
            </div>

            {/* Headline: Clean, Solid, Confident (Responsive Clamp Scale across all viewports) */}
            <div className="space-y-3">
              <h1 className="text-3xl xs:text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white leading-[1.08]">
                Your career pipeline. <br />
                <span className="text-orange-safety">Fully autonomous.</span>
              </h1>
              
              <p className="text-sm sm:text-base lg:text-lg text-slate-300 max-w-xl leading-relaxed">
                Two cooperative desktop agents running on your machine. <strong className="text-slate-100 font-semibold">Root-01</strong> navigates multi-page ATS portals and forms. <strong className="text-slate-100 font-semibold">Kernel-02</strong> resolves questions using deterministic 5-tier facts with zero hallucination.
              </p>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-wrap items-center gap-2.5 sm:gap-3 pt-1">
              <a
                href="#automation-demos"
                className="w-full sm:w-auto text-center px-6 py-3 rounded-lg bg-orange-safety text-white text-sm font-semibold hover:bg-orange-600 transition-colors flex items-center justify-center gap-2 shadow-sm"
              >
                <span>Watch Automation Demos</span>
              </a>
              <a
                href="https://github.com/Ahmad01Ansari/JobPilot/releases"
                target="_blank"
                rel="noopener noreferrer"
                className="w-full sm:w-auto text-center px-5 py-3 rounded-lg bg-slate-900 border border-slate-700 text-slate-200 text-sm font-medium hover:text-white hover:border-slate-500 transition-colors flex items-center justify-center gap-2"
              >
                <Download className="h-4 w-4 text-slate-400" />
                <span>Download Desktop Releases</span>
              </a>
            </div>

            {/* Embedded Fleet Communicator: Talk directly to Root-01 & Kernel-02 */}
            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 sm:p-5 backdrop-blur-md shadow-xl flex-1 flex flex-col justify-between mt-2">
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-3">
                <div className="flex items-center gap-2">
                  <Bot className="h-4 w-4 text-orange-safety" />
                  <span className="font-mono text-xs font-semibold text-slate-200 uppercase tracking-wider">
                    Fleet Communicator
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-[11px] font-mono text-slate-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  <span>2 Agents Synchronized</span>
                </div>
              </div>

              {/* Preset Chips */}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {PRESET_QUERIES.map((p, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSendPrompt(p.q)}
                    disabled={isBotResponding}
                    className="text-[10px] sm:text-[11px] font-mono px-2.5 py-1 rounded-md border border-slate-800 bg-slate-950/80 text-slate-300 hover:text-white hover:border-slate-600 transition-colors text-left"
                  >
                    {p.q}
                  </button>
                ))}
              </div>

              {/* Chat Thread */}
              <div className="my-3 max-h-[170px] sm:max-h-[200px] overflow-y-auto space-y-2.5 pr-1 text-xs font-mono scrollbar-thin scrollbar-thumb-slate-800">
                {chatHistory.map((msg, i) => (
                  <div
                    key={i}
                    className={`p-2.5 rounded-lg border ${
                      msg.sender === "You"
                        ? "bg-slate-800/70 border-slate-700/80 ml-4 sm:ml-6 text-slate-100"
                        : "bg-slate-950/90 border-slate-800/80 mr-2 sm:mr-4"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="font-semibold text-[11px]" style={{ color: msg.color }}>
                        {msg.sender}
                      </span>
                      <span className="text-[10px] text-slate-500 uppercase">{msg.role}</span>
                    </div>
                    <p className="text-slate-300 leading-relaxed text-[11px]">{msg.text}</p>
                  </div>
                ))}
              </div>

              {/* Input Bar */}
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendPrompt(userInput);
                }}
                className="flex gap-2 pt-2 border-t border-slate-800/60"
              >
                <input
                  type="text"
                  value={userInput}
                  onChange={(e) => setUserInput(e.target.value)}
                  placeholder="Ask Root & Kernel or enter target role..."
                  className="flex-1 rounded-lg bg-slate-950 border border-slate-800 px-3.5 py-2 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-slate-600 font-mono min-w-0"
                />
                <button
                  type="submit"
                  disabled={isBotResponding || !userInput.trim()}
                  className="rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-100 px-3.5 sm:px-4 py-2 text-xs font-medium flex items-center gap-1.5 transition-colors border border-slate-700 shrink-0"
                >
                  <span>Send</span>
                  <Send className="h-3 w-3 text-slate-400" />
                </button>
              </form>
            </div>

          </div>

          {/* Right Column (5 cols): The Dual-Robot Cockpit */}
          <div className="lg:col-span-5 flex flex-col justify-between">
            <div className="relative w-full h-[400px] sm:h-[480px] lg:h-full min-h-[380px] sm:min-h-[480px] rounded-2xl border border-slate-800 bg-slate-900/40 backdrop-blur-md overflow-hidden shadow-2xl flex flex-col items-center justify-between p-3.5 sm:p-4">
              
              {/* Top View Mode Switcher Pill */}
              <div className="w-full flex items-center justify-between z-30 px-1 sm:px-2 pt-1 pointer-events-auto">
                <div className="flex items-center gap-1.5 sm:gap-2 font-mono text-[10px] sm:text-[11px] text-slate-400">
                  <span className="h-2 w-2 rounded-full bg-emerald-400" />
                  <span>Dual Autonomous Cockpit</span>
                </div>
                <div className="flex items-center gap-1 bg-slate-950/90 border border-slate-800 rounded-lg p-0.5 text-[10px] sm:text-[11px] font-mono shadow-sm">
                  <button
                    type="button"
                    onClick={() => setViewMode("3d")}
                    className={`px-2 sm:px-2.5 py-1 rounded-md transition-all ${
                      viewMode === "3d" || (viewMode === "auto" && hasWebGL)
                        ? "bg-slate-800 text-white font-semibold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    3D WebGL
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode("vector")}
                    className={`px-2 sm:px-2.5 py-1 rounded-md transition-all ${
                      viewMode === "vector" || (viewMode === "auto" && !hasWebGL)
                        ? "bg-slate-800 text-white font-semibold"
                        : "text-slate-400 hover:text-white"
                    }`}
                  >
                    HD Spherical
                  </button>
                </div>
              </div>

              {/* Floating Interactive Speech Badges */}
              <div className="w-full flex justify-between items-start pointer-events-none z-20 px-1 sm:px-2 mt-2 gap-2">
                <div
                  onClick={() => handleSendPrompt("Root, what are you scanning right now?")}
                  className="pointer-events-auto max-w-[140px] xs:max-w-[160px] sm:max-w-[185px] bg-slate-950/95 border border-slate-800 p-2 sm:p-2.5 rounded-xl shadow-lg cursor-pointer hover:border-orange-500/50 transition-colors select-none"
                  title="Click to talk to Root-01"
                >
                  <div className="flex items-center gap-1 sm:gap-1.5 mb-0.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-orange-safety shrink-0" />
                    <span className="text-[9px] sm:text-[10px] font-mono font-bold text-orange-400 truncate">Root-01 // Navigator</span>
                  </div>
                  <p className="text-[9px] sm:text-[10px] text-slate-300 leading-tight">
                    "Greenhouse &amp; Lever parsed. Form ready."
                  </p>
                </div>

                <div
                  onClick={() => handleSendPrompt("Kernel, how do you verify answers?")}
                  className="pointer-events-auto max-w-[140px] xs:max-w-[160px] sm:max-w-[185px] bg-slate-950/95 border border-slate-800 p-2 sm:p-2.5 rounded-xl shadow-lg cursor-pointer hover:border-cyan-500/50 transition-colors select-none text-right"
                  title="Click to talk to Kernel-02"
                >
                  <div className="flex items-center justify-end gap-1 sm:gap-1.5 mb-0.5">
                    <span className="text-[9px] sm:text-[10px] font-mono font-bold text-cyan-400 truncate">Kernel-02 // 5-Tier</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0" />
                  </div>
                  <p className="text-[9px] sm:text-[10px] text-slate-300 leading-tight">
                    "Verified facts mapped. Zero hallucination."
                  </p>
                </div>
              </div>

              {/* Center Robot Canvas / Vector Stage */}
              <div className="relative w-full flex-1 flex items-center justify-center">
                {mounted && (viewMode === "3d" || (viewMode === "auto" && hasWebGL)) ? (
                  <RobotErrorBoundary
                    fallback={
                      <div className="w-full flex items-center justify-center gap-8 py-4">
                        <AnimatedRobotSvg
                          color="#ff7a00"
                          name="Root-01"
                          status="Portal Navigator"
                          isThinking={isBotResponding}
                          onClick={() => handleSendPrompt("Root, scan status?")}
                        />
                        <AnimatedRobotSvg
                          color="#00ffc6"
                          name="Kernel-02"
                          status="5-Tier Q&A Engine"
                          isThinking={isBotResponding}
                          onClick={() => handleSendPrompt("Kernel, Q&A status?")}
                        />
                      </div>
                    }
                  >
                    <div className="absolute inset-0">
                      <Canvas
                        camera={{ position: [0, 0.15, 4.3], fov: 42 }}
                        gl={{ antialias: true, alpha: true, powerPreference: "default" }}
                      >
                        <ambientLight intensity={1.3} color="#ffffff" />
                        <directionalLight position={[0, 8, 5]} intensity={1.5} color="#ffffff" />
                        <directionalLight position={[-5, 3, 2]} intensity={1.1} color="#ff7a00" />
                        <directionalLight position={[5, 3, 2]} intensity={1.1} color="#00ffc6" />
                        <pointLight position={[0, -0.1, 2.5]} intensity={0.6} color="#ffffff" />

                        <React.Suspense fallback={null}>
                          <ResponsiveGroup scale={1.2}>
                            <mesh position={[-0.72, -0.74, 0]} rotation={[-Math.PI / 2, 0, 0]}>
                              <circleGeometry args={[0.55, 32]} />
                              <meshBasicMaterial color="#000000" transparent opacity={0.45} />
                            </mesh>
                            <mesh position={[0.72, -0.74, 0]} rotation={[-Math.PI / 2, 0, 0]}>
                              <circleGeometry args={[0.55, 32]} />
                              <meshBasicMaterial color="#000000" transparent opacity={0.45} />
                            </mesh>
                            <RobotPrototype
                              position={[-0.72, -0.22, 0]}
                              color="#f8fafc"
                              pantallaColor="#ff7a00"
                              pantallaBrillo={2.0}
                              antennaColor="#ff7a00"
                              blinkCycle={3.2}
                              metalness={0.12}
                              targetOffset={-0.25}
                              onRobotClick={() => handleSendPrompt("Root, scan status?")}
                            />
                            <RobotPrototype
                              position={[0.72, -0.22, 0]}
                              color="#e2e8f0"
                              pantallaColor="#00ffc6"
                              pantallaBrillo={2.0}
                              antennaColor="#00ffc6"
                              blinkCycle={2.8}
                              metalness={0.18}
                              targetOffset={0.25}
                              onRobotClick={() => handleSendPrompt("Kernel, Q&A status?")}
                            />
                          </ResponsiveGroup>
                        </React.Suspense>
                      </Canvas>
                    </div>
                  </RobotErrorBoundary>
                ) : (
                  <div className="w-full flex items-center justify-center gap-6 sm:gap-10 py-4 z-10">
                    <AnimatedRobotSvg
                      color="#ff7a00"
                      name="Root-01"
                      status="Portal Navigator"
                      isThinking={isBotResponding}
                      onClick={() => handleSendPrompt("Root, scan status?")}
                    />
                    <AnimatedRobotSvg
                      color="#00ffc6"
                      name="Kernel-02"
                      status="5-Tier Q&A Engine"
                      isThinking={isBotResponding}
                      onClick={() => handleSendPrompt("Kernel, Q&A status?")}
                    />
                  </div>
                )}
              </div>

              {/* Bottom Real Engine Telemetry Rail */}
              <div className="w-full grid grid-cols-2 gap-2 pt-3 border-t border-slate-800/80 font-mono text-[10px] text-slate-400 z-20">
                <div className="flex items-center gap-1.5 bg-slate-950/70 border border-slate-800 px-2.5 py-1.5 rounded-lg">
                  <span className="w-1.5 h-1.5 rounded-full bg-orange-safety" />
                  <span className="truncate">Root: Greenhouse • Lever • Foundit</span>
                </div>
                <div className="flex items-center gap-1.5 bg-slate-950/70 border border-slate-800 px-2.5 py-1.5 rounded-lg">
                  <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
                  <span className="truncate">Kernel: 5-Tier Q&amp;A Local Vault</span>
                </div>
              </div>

            </div>
          </div>

        </div>

        {/* Full-Width Engineering Spec Grid (Bottom Edge) */}
        <div className="mt-10 grid grid-cols-1 sm:grid-cols-3 gap-6 pt-6 border-t border-slate-800 font-mono text-xs text-slate-400">
          <div className="flex items-start gap-3">
            <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-slate-200">100% Local SQLite Vault</p>
              <p className="text-[11px] text-slate-400 mt-0.5">All credentials, resume variants, and logs stay on your local disk.</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <Terminal className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-slate-200">5-Tier Deterministic Q&amp;A</p>
              <p className="text-[11px] text-slate-400 mt-0.5">Answers verified against profile facts. Never hallucinated.</p>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <CheckCircle2 className="h-4 w-4 text-orange-400 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold text-slate-200">Mandatory Human Checkpoints</p>
              <p className="text-[11px] text-slate-400 mt-0.5">Automations pause for review before sensitive submissions.</p>
            </div>
          </div>
        </div>

      </div>

    </section>
  );
}

export default RobotHero;
