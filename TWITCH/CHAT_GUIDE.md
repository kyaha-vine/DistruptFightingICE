# 🎮 Twitch Chat Bot - User Guide

## How to Participate

### Step 1: Wait for Voting Round (30 seconds)
When a round starts, you can vote for an item:

```
!item freeze    (🧊 Freeze Orb)
!item fire      (🔥 Power Core)
!item wind      (💨 Wind Boots)
!item shield    (🧱 Shield Stone)
!item chaos     (🎭 Chaos Mask)
```

### Step 2: **WAIT** for Round to End
⏰ **Important**: You must wait the full 30 seconds for voting to finish!

### Step 3: Winner is Chosen
- The item with most votes wins
- One random voter who voted for that item is selected
- The bot announces: `[username] can place [item]`

### Step 4: Winner Places Item (if you won)
**Only if you are the chosen winner**, you can now type:

```
!place left
!place middle
!place right
```

## ❌ Common Mistake

**DON'T DO THIS:**
```
!item fire        ← Vote
!place right      ← TOO EARLY! Round hasn't ended yet
```

**DO THIS:**
```
!item fire        ← Vote
[wait 30 seconds for round to end]
[Bot announces you won]
!place right      ← NOW you can place!
```

## Timing Example

```
00:00 - Round 16 starts
00:05 - You: !item fire ✓
00:10 - Other votes coming in...
00:20 - Still voting...
00:30 - Round ends!
00:30 - Bot: "thienduongkhacbot won! Place your item!"
00:35 - You: !place right ✓ SUCCESS!
```

## Additional Commands

- `!items` - See list of available items

## Tips

1. **Vote early** during the 30-second window
2. **Be patient** - wait for the round to finish
3. **Watch for your name** - bot will say if you won
4. **Place quickly** - you have about 5 seconds before next round starts
