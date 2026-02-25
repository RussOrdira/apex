import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'screens/home_screen.dart';
import 'screens/leaderboard_screen.dart';
import 'screens/predictions_screen.dart';
import 'screens/profile_screen.dart';

void main() {
  runApp(const ProviderScope(child: ApexPredictApp()));
}

class ApexPredictApp extends StatelessWidget {
  const ApexPredictApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Apex Predict',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF0F766E)),
        useMaterial3: true,
      ),
      home: const RootNavScreen(),
    );
  }
}

class RootNavScreen extends StatefulWidget {
  const RootNavScreen({super.key});

  @override
  State<RootNavScreen> createState() => _RootNavScreenState();
}

class _RootNavScreenState extends State<RootNavScreen> {
  int _index = 0;

  final _screens = const [
    HomeScreen(),
    PredictionsScreen(),
    LeaderboardScreen(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _screens[_index],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (index) => setState(() => _index = index),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.flag), label: 'Home'),
          NavigationDestination(icon: Icon(Icons.auto_graph), label: 'Predict'),
          NavigationDestination(icon: Icon(Icons.leaderboard), label: 'Leagues'),
          NavigationDestination(icon: Icon(Icons.person), label: 'Profile'),
        ],
      ),
    );
  }
}
