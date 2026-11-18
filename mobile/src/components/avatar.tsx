/**
 * The learner's avatar: a gradient and a geometric motif generated from their seed, with their
 * initial on top. Unique per learner, identical on every device, drawn without images.
 */
import { LinearGradient } from 'expo-linear-gradient';
import { StyleSheet, Text, View } from 'react-native';

import { Fonts } from '@/constants/theme';
import { avatarSpec, initialOf } from '@/utils/avatar';

export function Avatar({ seed, name, size = 44, label }: { seed: string; name: string; size?: number; label?: string }) {
  const spec = avatarSpec(seed);
  const letter = initialOf(name);
  const m = size / 44;
  return <View accessible={!!label} accessibilityRole={label ? 'image' : undefined} accessibilityLabel={label}
    accessibilityElementsHidden={!label} importantForAccessibility={label ? 'yes' : 'no-hide-descendants'}
    style={[styles.frame, { width: size, height: size, borderRadius: size / 2 }]}>
    <LinearGradient colors={spec.colors} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={StyleSheet.absoluteFill} />
    <View style={[StyleSheet.absoluteFill, styles.center, { transform: [{ rotateZ: `${spec.angle}deg` }] }]}>
      <Motif kind={spec.motif} m={m} />
    </View>
    {letter ? <Text style={[styles.letter, { fontSize: 19 * m, textShadowRadius: 4 * m }]}>{letter}</Text> : null}
  </View>;
}

function Motif({ kind, m }: { kind: ReturnType<typeof avatarSpec>['motif']; m: number }) {
  const glass = 'rgba(255,255,255,0.28)';
  const faint = 'rgba(255,255,255,0.16)';
  switch (kind) {
    case 'diamond':
      return <>
        <View style={{ position: 'absolute', width: 30 * m, height: 30 * m, borderRadius: 7 * m, backgroundColor: faint, transform: [{ rotateZ: '45deg' }] }} />
        <View style={{ position: 'absolute', width: 16 * m, height: 16 * m, borderRadius: 4 * m, backgroundColor: glass, transform: [{ rotateZ: '45deg' }, { translateX: 12 * m }] }} />
      </>;
    case 'orbit':
      return <>
        <View style={{ position: 'absolute', width: 36 * m, height: 16 * m, borderRadius: 99, borderWidth: 2.5 * m, borderColor: glass }} />
        <View style={{ position: 'absolute', width: 9 * m, height: 9 * m, borderRadius: 99, backgroundColor: glass, transform: [{ translateX: 17 * m }] }} />
      </>;
    case 'petal':
      return <>
        {[0, 90, 180, 270].map(r => <View key={r} style={{ position: 'absolute', width: 14 * m, height: 26 * m, borderRadius: 99, backgroundColor: faint,
          transform: [{ rotateZ: `${r}deg` }, { translateY: -9 * m }] }} />)}
      </>;
    case 'stack':
      return <>
        <View style={{ position: 'absolute', width: 26 * m, height: 18 * m, borderRadius: 5 * m, backgroundColor: faint, transform: [{ rotateZ: '-14deg' }, { translateY: 6 * m }] }} />
        <View style={{ position: 'absolute', width: 26 * m, height: 18 * m, borderRadius: 5 * m, backgroundColor: glass, transform: [{ rotateZ: '10deg' }, { translateY: -6 * m }] }} />
      </>;
  }
}

const styles = StyleSheet.create({
  frame: { overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  center: { alignItems: 'center', justifyContent: 'center' },
  letter: { fontFamily: Fonts.display, color: '#ffffff', textShadowColor: 'rgba(0,0,0,0.18)', textShadowOffset: { width: 0, height: 1 } },
});
