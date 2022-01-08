SELECT(
    UPDATE Guild
    FILTER .discord_id = <bigint>$guild_id
    SET {
        name := <bounded_str>$guild_name,
    }
)
{
    id,
    discord_id,
    guild_id,
    name,
    channels: {
        discord_id,
        channel_id,
        name,
    },
    members: {
        discord_id,
        user_id,
        name,
        discriminator,
        full_tag,
        is_owner,
        is_bot,
        dm_channel,
    },
};