import 'package:flutter/material.dart';

class PredictionsScreen extends StatelessWidget {
  const PredictionsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const SafeArea(
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Predictions', style: TextStyle(fontSize: 30, fontWeight: FontWeight.bold)),
            SizedBox(height: 12),
            Text(
              'Session question packs and confidence-credit submission UI will be rendered here.',
            ),
          ],
        ),
      ),
    );
  }
}
