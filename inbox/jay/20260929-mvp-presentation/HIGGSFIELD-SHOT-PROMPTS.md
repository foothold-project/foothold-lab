# Higgsfield 컷별 연출 문안

> 분류: 계획
> 작성: Codex · 2026-09-30 21:00
> 근거: 사용자 최신 조명 참고·바닥 카메라 통과·정면 앉기 요청
> 요지: E2는 고정광 분위기 공개, E5는 낮은 카메라 통과 후 후면 오르기와 정면 앉기로 연결한다.
> 상태: E2 참조 기반 이미지 시안 제작 · 영상 문안 준비 · 영상 미제출
> 판: v0.3

이슈: [#490](https://github.com/foothold-project/foothold-lab/issues/490). 이전 E2 탐색광과 E5 후면 앉기 설계를 대체한다. 현재 HTML은 정지 이미지 전환이며 아래 동작을 실제 영상으로 생성한 것은 아니다.

## 공통 생성 조건 · 최신 기준

O1의 손전등 표현은 빛의 움직임을 이해시키기 위한 비유다. 실제 손전등 소품·손·사람을 생성하지 않는다. E2는 탐색광이 아니라 고정된 빛 속으로 Go2가 걸어 들어오는 장면이다. 캐릭터 시트 적용 후 E2 이미지부터 확인하며, 다른 컷과 영상 일괄 생성은 아직 승인 범위가 아니다.

[전체 연출 점검](FILM-DIRECTOR-NOTES.md)을 함께 따른다. Seedance 초안은 `generate_audio=true`로 현장 소리를 포함한다. 전체 사운드는 이후 새로 구성·믹싱한다. 아래 문안은 기존 정지 원화가 동작을 완성했다는 뜻이 아니다.

```text
Photographic realism with restrained local contrast and natural highlight roll-off. Preserve deep shadows. Uneven surface roughness, worn paint, localized grime and small scratches; concrete has distinct dry, damp and puddled regions. No exaggerated HDR, glossy plastic robot, universal mirror-wet surfaces or oversharpened edges. Match the same approved Go2 identity reference in every shot, including leg link thickness, joint housings and black foot rubber shape. Sparse occasional water drips with local ripples; thin slow mist that never hides critical foot contacts. Generate synchronized diegetic audio: actual footsteps, restrained servos, water and consistent large-room ambience. No dialogue, lyrics, vocals or independent music score for this individual clip. No random alarm beeps. Final music and sound design will be composed across the entire edit.
```

## E2 · 고정된 빛 속 실루엣 공개

사용자 참고 2건을 직접 확인했다. 넓은 어둠 속 집중된 빛과 실루엣이 핵심이다. 두 번째 참고는 사용자가 정확한 예시가 아니라고 했으므로 그대로 따르지 않는다. O1의 탐색광은 유지하되 E2에서는 빛을 움직이지 않는다.

기존 원화 v6는 조명 방향 참고다. 새 동작은 로봇이 더 뒤쪽 어둠에서 빛 안으로 걸어 나온다. 영상 제작 전 시작 프레임의 로봇을 뒤로 배치하고 주변을 더 어둡게 맞춘다. 현재 같은 위치의 두 원화를 그대로 시작·끝에 고정하지 않는다. 끝은 assets/ending-e2-mood-end-v6.png의 중앙 중경 위치. 기본 5초 후보.

```text
One continuous 5-second cinematic reveal, 16:9. Locked frontal camera, slightly elevated, looking into a vast almost black ruined industrial hall. A fixed overhead/backlight remains visible as a restrained shaft in thin haze. Go2 begins farther back in deep darkness, only a faint silhouette. The same matte light-gray Unitree Go2 quadruped walks slowly forward along the central axis, entering the fixed pool of light until its face, shell and limbs become clearly readable in the central midground. Reveal the robot THROUGH ITS MOTION into light, not by a sweeping flashlight or global exposure ramp. Stop before it becomes a foreground close-up. Consistent four-legged gait and contact, no gliding. Light direction and camera remain stable. No torch, searching beam, orbit, zoom, teleportation, human, text or HUD. Sparse distant drips and footfalls approach naturally; restrained motor sound and room reverberation, no music or speech.
```

## E5pre · 바닥 카메라 위를 통과

기존 assets/ending-e5-step-v1.png를 복원한다. 카메라는 목표를 향해 바닥에 고정돼 있고, Go2가 카메라 뒤에서 앞으로 지나간다. 기본 5초 후보. 몸통 가림과 발소리로 거리감을 만들고, 턱 앞 발 들림에서 다음 컷으로 잇는다.

```text
One continuous 5-second cinematic ground-camera shot, 16:9. Match the supplied low floor-level view toward the rusty inspection cabinet with the red beacon and low concrete threshold. Camera is fixed a few centimeters above the wet approach floor, looking forward at the target. Begin with the empty walkway. The silver Unitree Go2 enters from BEHIND the camera and walks directly OVER it, continuing AWAY toward the cabinet. The robot naturally crosses over the low camera position without choreographing feet symmetrically around the lens. The passing body briefly occludes part of the view and then clears it; allow physically plausible foot placement and safe camera clearance. The robot clears the lens and its rear silhouette approaches the step, revealing the target again. Four coherent mechanical legs, correct foot contacts, believable weight transfer, subtle small splashes. No sliding, extra limbs, camera collision, transparent robot, camera movement, HUD or text. End approaching the curb for a cut into the ascent.
```

## E5 · 뒤에서 턱 오르기

원화: assets/ending-e5a-climb-centered-v2.png. 기본 5초 후보.

```text
Centered straight rear view of the same Unitree Go2 ascending the low concrete threshold toward the same inspection cabinet. Front feet plant on the upper landing, rear legs push the body up, then each rear foot clears the riser and plants on top. No leap, foot penetration or sliding. Continue one or two short steps toward the target on the upper landing. Maintain a steady camera and the same axis. Slow as the robot reaches its observation position. Four mechanically coherent limbs throughout. No text or HUD. Cut just BEFORE the sitting motion begins. Match the last standing position and slowing body movement to a frontal shot in which the sitting action takes place.
```

## E5b · 조금 높은 정면 원경에서 앉기

끝 원화: assets/ending-e5b-seated-front-v3.png. 같은 구도의 앉기 직전 시작 원화는 영상 제작 전 추가할 대상이다. 뒤에서 본 로봇을 한 컷 안에서 정면으로 변형시키지 않고 컷으로 카메라를 바꾼다. 목표 설비는 카메라 뒤에 있으므로 로봇 뒤에 다시 등장하지 않는다. 이전의 정면 컷 생략 판단은 최신 사용자 요청으로 대체한다.

```text
One continuous frontal cinematic shot, 16:9. Camera slightly above the robot looking gently downward from a moderate distance. Silver Go2 centered and relatively small in frame with the ruined hall visible around it. Camera is near the inspection equipment, looking back along the route the robot traveled. Equipment and red beacon are behind the camera, never behind the robot. Begin after its final short step on the upper landing. It stops facing the target, then folds BOTH hind legs and lowers its rear pelvis while BOTH front legs remain planted and extended supporting the raised chest. Hold the seated pose looking toward the target just beyond camera. Exactly four mechanical limbs, no human pose, tail or identity change. Locked square-on camera, no side angle, orbit or exaggerated lens distortion. Finish with stable gaze motivating a cut to target POV. No HUD or text.
```

## 원화와 확인 범위

새 원화 3장은 built-in image_gen으로 제작했다. 각 png 옆 동일 이름 prompt.txt에 원문을 저장했다. 실제 동역학·접지·관절 가동 범위를 검증한 결과는 아니다. 영상에서 빛의 고정, 카메라 통과 시 충돌·투명화 여부, 턱 접촉 순서, 앞다리 지지와 뒷다리 접힘, 목표 방향을 확인한다. HUD와 전체 사운드는 별도 제작한다.

참고 사진 자체를 결과에 복제하지 않았다.

- [첫 조명 참고](https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRh7ehesHuWIQs3Fvnl5VDJx-HtCZYiIlMvlsJWdC7CtQ&s=10)
- [두 번째 분위기 참고](https://images.unsplash.com/photo-1708445634891-fcb73d2c1338)

## 환경·관측 그래픽 문안

```text
The distant red warning beacon has a slow consistent intensity pulse, reflected subtly on nearby wet surfaces. No scanning laser. During a gap crossing, a few tiny chips dislodge from the rim in response to foot contact and fall down the gap; damp fragments near wet concrete, minimal dry dust only from a dry exposed edge. No collapsing platform or explosive debris. Preserve target location and terrain dimensions between shots.
```

HUD는 별도 그래픽으로 정확히 합성한다. 자세·속도·관측 갱신을 화면 움직임에 맞추되 실제 로그 없는 값을 실측이라고 표기하지 않는다. scan은 지형에 고정하고 빈 틈을 연결하지 않는다. 컷별 소리는 유지해서 받은 뒤 하나의 공간·음악·효과음 체계로 재구성한다.

## 판 이력

| 판 | 날짜 | 변경 |
|---|---|---|
| v0.2 | 2026-09-30 | E2 뒤에서 걸어 나옴, 더 어두운 시작, E5 발 위치 강제 제거·앉기 직전 컷, 원본 소리 포함·사진 재질 기준 |
| v0.1 | 2026-09-30 | 고정광 공개·바닥 카메라 통과·정면 앉기 이미지와 영상 문안 |
| v0.3 | 2026-09-30 | 손전등 소품 배제, 공식 회색 Go2 외형과 이미지 우선 승인 범위 명시 |
