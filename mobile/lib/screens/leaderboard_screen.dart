import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/types.dart';
import '../services/api_client.dart';

final globalLeaderboardProvider = FutureProvider<List<LeaderboardRowModel>>((ref) async {
  return ref.watch(apiClientProvider).globalLeaderboard();
});

class LeaderboardScreen extends ConsumerWidget {
  const LeaderboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final boardAsync = ref.watch(globalLeaderboardProvider);

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Global Leaderboard', style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 16),
            Expanded(
              child: boardAsync.when(
                data: (rows) {
                  if (rows.isEmpty) {
                    return const Center(child: Text('No scores yet.'));
                  }
                  return ListView.separated(
                    itemCount: rows.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final row = rows[index];
                      return ListTile(
                        leading: CircleAvatar(child: Text('${row.rank}')),
                        title: Text(row.username),
                        trailing: Text(row.totalPoints.toStringAsFixed(1)),
                      );
                    },
                  );
                },
                loading: () => const Center(child: CircularProgressIndicator()),
                error: (error, _) => Center(child: Text('Could not load leaderboard: $error')),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
