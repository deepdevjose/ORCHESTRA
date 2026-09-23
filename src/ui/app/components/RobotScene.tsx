"use client";

import { useEffect, useRef, useState } from "react";
import type { Object3D, WebGLRenderer } from "three";

export default function RobotScene() {
  const mountRef = useRef<HTMLDivElement>(null);
  const [loadState, setLoadState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let disposed = false;
    let frameId = 0;
    let renderer: WebGLRenderer | undefined;
    let robot: Object3D | null = null;

    async function createScene() {
      const mount = mountRef.current;
      if (!mount) return;

      const THREE = await import("three");
      const { GLTFLoader } = await import("three/examples/jsm/loaders/GLTFLoader.js");
      const { DRACOLoader } = await import("three/examples/jsm/loaders/DRACOLoader.js");
      if (disposed || !mountRef.current) return;

      const scene = new THREE.Scene();
      scene.background = new THREE.Color(0xe9eef3);
      scene.fog = new THREE.Fog(0xe9eef3, 8, 22);

      const camera = new THREE.PerspectiveCamera(28, 1, 0.01, 1000);
      camera.position.set(4.6, 2.9, 5.8);
      camera.lookAt(0, 0.28, 0);

      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.outputColorSpace = THREE.SRGBColorSpace;
      renderer.shadowMap.enabled = true;
      renderer.shadowMap.type = THREE.PCFSoftShadowMap;
      mount.appendChild(renderer.domElement);

      scene.add(new THREE.HemisphereLight(0xffffff, 0x9aa9b8, 2.2));
      const keyLight = new THREE.DirectionalLight(0xffffff, 3.4);
      keyLight.position.set(4, 8, 5);
      keyLight.castShadow = true;
      scene.add(keyLight);
      const rimLight = new THREE.DirectionalLight(0x2f7de1, 2.3);
      rimLight.position.set(-5, 3, -4);
      scene.add(rimLight);

      const floor = new THREE.Mesh(
        new THREE.CircleGeometry(4.2, 64),
        new THREE.MeshStandardMaterial({ color: 0xd7dee5, roughness: 0.94, metalness: 0.04 }),
      );
      floor.rotation.x = -Math.PI / 2;
      floor.position.y = -0.30;
      floor.receiveShadow = true;
      scene.add(floor);

      const grid = new THREE.GridHelper(7.5, 24, 0xb8c5d1, 0xd0d9e1);
      grid.position.y = -0.28;
      scene.add(grid);

      const dracoLoader = new DRACOLoader();
      dracoLoader.setDecoderPath("/draco/");
      const loader = new GLTFLoader();
      loader.setDRACOLoader(dracoLoader);
      loader.load(
        "/3D_models/siasunsr12a.glb",
        (gltf) => {
          if (disposed) return;
          robot = gltf.scene;
          const bounds = new THREE.Box3().setFromObject(robot);
          const center = bounds.getCenter(new THREE.Vector3());
          const size = bounds.getSize(new THREE.Vector3());
          const maxDimension = Math.max(size.x, size.y, size.z) || 1;
          const scale = 3.3 / maxDimension;
          robot.scale.setScalar(scale);
          robot.position.sub(center.multiplyScalar(scale));
          robot.position.y += 0.18;
          robot.rotation.y = -0.58;
          robot.traverse((child) => {
            if (child instanceof THREE.Mesh) {
              child.castShadow = true;
              child.receiveShadow = true;
            }
          });
          scene.add(robot);
          setLoadState("ready");
        },
        undefined,
        () => setLoadState("error"),
      );

      const resize = () => {
        if (!renderer || !mountRef.current) return;
        const width = mountRef.current.clientWidth || 1;
        const height = mountRef.current.clientHeight || 1;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize(width, height, false);
      };
      resize();
      const observer = new ResizeObserver(resize);
      observer.observe(mount);

      const animate = (time: number) => {
        if (disposed || !renderer) return;
        if (robot) robot.rotation.y = -0.58 + Math.sin(time * 0.00018) * 0.18;
        renderer.render(scene, camera);
        frameId = requestAnimationFrame(animate);
      };
      frameId = requestAnimationFrame(animate);

      return () => {
        observer.disconnect();
        dracoLoader.dispose();
      };
    }

    let cleanup: (() => void) | undefined;
    void createScene()
      .then((disposeResizeObserver) => { cleanup = disposeResizeObserver; })
      .catch(() => { if (!disposed) setLoadState("error"); });
    return () => {
      disposed = true;
      cancelAnimationFrame(frameId);
      cleanup?.();
      renderer?.dispose();
      if (renderer?.domElement.parentNode === mountRef.current) renderer.domElement.remove();
    };
  }, []);

  return (
    <div className="robot-scene" ref={mountRef} data-testid="robot-scene" aria-label="Interactive SIASUN SR12A robot model">
      {loadState === "loading" && <div className="scene-state">Loading asset</div>}
      {loadState === "error" && <div className="scene-state scene-error">3D asset unavailable</div>}
      <div className="scene-caption"><span>SIASUN</span><strong>SR12A</strong></div>
    </div>
  );
}
