import 'package:flutter/material.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const SafeArea(
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Profile', style: TextStyle(fontSize: 30, fontWeight: FontWeight.bold)),
            SizedBox(height: 12),
            Text('Username, total points, and category accuracy badges will appear here.'),
          ],
        ),
      ),
    );
  }
}
