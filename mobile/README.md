# Apex Predict Mobile Skeleton

This is a Flutter-ready shell for iOS/Android with:
- bottom navigation
- event list screen (`/v1/events`)
- global leaderboard screen (`/v1/leaderboards/global`)
- placeholder predictions/profile screens

## Run

1. Install Flutter SDK.
2. From this directory:

```bash
flutter pub get
flutter run --dart-define=APEX_API_BASE_URL=http://localhost:8000/v1
```
