import type { ReactNode } from 'react';
import { Clock3, Grid3x3, ListOrdered, Lock, Megaphone, Mic2, Phone, PhoneIncoming, PhoneMissed, PhoneOff, PhoneOutgoing, Shuffle, SunMoon, Users, Voicemail } from 'lucide-react';
import type { DestKind } from '@/domain/destination';
import { useEnumText } from '@/lib/useEnumText';

/** Har manzil turining ikoni — picker, oqim grafigi va jadvallarda bir xil. */
export const KIND_ICON: Record<DestKind | 'did', ReactNode> = {
  did: <PhoneIncoming />,
  extension: <Phone />,
  ring_group: <Users />,
  queue: <ListOrdered />,
  ivr: <Grid3x3 />,
  time_condition: <Clock3 />,
  conference: <Mic2 />,
  voicemail: <Voicemail />,
  announcement: <Megaphone />,
  misc: <Shuffle />,
  external: <PhoneOutgoing />,
  hangup: <PhoneOff />,
  busy: <PhoneMissed />,
  day_night: <SunMoon />,
  disa: <Lock />,
};

export const KIND_ORDER: DestKind[] = [
  'extension', 'ring_group', 'queue', 'ivr', 'time_condition', 'conference', 'voicemail', 'announcement', 'misc', 'day_night', 'disa', 'external', 'hangup', 'busy',
];

/**
 * M1a bosqichida DestinationPicker'da ko'rsatiladigan turlar (`../../replica/m1a-contract.md`): announcement/voicemail/external keyingi bosqich.
 * M2a (`../../replica/m2a-contract.md` §4) konferensiyani qo'shadi — nom o'zgarmaydi, tarkibi kengaygan.
 * M9 (`../../replica/m9-freepbx-gaps-contract.md` §A1/§A2) e'lon va boshqa manzillarni qo'shadi.
 * M12 A1/A2 (`../../replica/m12-contract.md` §A1/§A2) kun/tun rejimi va DISA'ni qo'shadi.
 */
export const M1A_KINDS: DestKind[] = ['extension', 'ring_group', 'queue', 'ivr', 'time_condition', 'conference', 'hangup', 'busy', 'announcement', 'misc', 'day_night', 'disa'];

/** Har manzil turining tarjima qilingan nomi (`common.kind.*`) — til almashganda darhol yangilanadi. */
export function useKindLabel(): Record<DestKind, string> {
  return useEnumText('common', 'kind', KIND_ORDER);
}
