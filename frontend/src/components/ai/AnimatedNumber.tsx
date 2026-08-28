import { motion, useSpring, useTransform, animate } from 'framer-motion';
import { useEffect, useState } from 'react';

interface AnimatedNumberProps {
  value: number;
  prefix?: string;
  suffix?: string;
  formatFn?: (value: number) => string;
  duration?: number;
  className?: string;
}

export default function AnimatedNumber({
  value,
  prefix = '',
  suffix = '',
  formatFn,
  duration = 800,
  className = '',
}: AnimatedNumberProps) {
  const spring = useSpring(value, {
    stiffness: 150,
    damping: 20,
    mass: 0.5,
  });

  const display = useTransform(spring, (current) => {
    let val = Math.round(current);
    if (formatFn) return formatFn(current);
    if (val >= 10000) return `${prefix}${(val / 10000).toFixed(1)}万${suffix}`;
    return `${prefix}${val.toLocaleString()}${suffix}`;
  });

  const [text, setText] = useState('');

  useEffect(() => {
    spring.set(value);
    const unsubscribe = display.on('change', (latest) => {
      setText(latest as string);
    });
    return () => unsubscribe();
  }, [value, spring, display]);

  return <span className={className}>{text}</span>;
}
