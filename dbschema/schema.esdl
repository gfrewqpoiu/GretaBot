module default {
    scalar type bounded_str extending str {
        constraint min_len_value(1);
        constraint max_len_value(300);
    }
    abstract type Quote {
        required property keyword -> bounded_str;
        required property quote_text -> str {
            constraint min_len_value(1);
            constraint max_len_value(1700);
        }
        required property created_at -> datetime{
            readonly := True;
            default := datetime_current();
        }
        property last_used_at -> datetime;
        required property times_used -> int32 {
            constraint min_value(0);
            default := 0;
        }
        single link last_used_by -> User;
        single link created_by -> User;
        single link last_used_in -> Snowflake;
    }
    type GlobalQuote extending Quote {
        overloaded required property keyword -> bounded_str {
            constraint exclusive;
        }
    }
    type GuildQuote extending Quote{
        required single link guild -> Guild {
            readonly := True;
        }
        # Just an alias for GuildQuote.guild.discord_id
        required property guild_id := .guild.discord_id;
    }
    type ChannelQuote extending Quote {
        required single link channel -> Channel {
            readonly := True;
        }
        # Just an alias for ChannelQuote.channel.discord_id
        required property channel_id := .channel.discord_id;
    }
    abstract type Snowflake {
        required property discord_id -> bigint {
            constraint exclusive;
            constraint min_value(0n);
            readonly := True;
        }
        property created_at -> datetime {
            readonly := True;
        };
    }
    type User extending Snowflake {
        required property name -> bounded_str;
        required property tag -> bounded_str;
        required property is_owner -> bool {
            default := False;
        }
        # Just an alias for User.discord_id
        required property user_id := .discord_id;
        # This is the really crazy stuff, links in EdgeDB are bidirectional.
        # So this allows us to fill guilds from the Guilds.
        multi link guilds := .<users[IS Guild]
    }
    abstract type Channel extending Snowflake{
        # Just an alias for Channel.discord_id
        required property channel_id := .discord_id;
    }
    type GuildChannel extending Channel {
        property name -> bounded_str {
            constraint min_len_value(0);
        }
        required single link guild -> Guild {
            readonly := True;
        }
    }
    type Guild extending Snowflake {
        required property name -> bounded_str;
        multi link users -> User;
        # Just an alias for Guild.discord_id
        required property guild_id := .discord_id;
        # Again crazy, we can fill channels automatically from the known channels of this guild.
        multi link channels := .<guild[IS GuildChannel];
    }
    type DMChannel extending Channel {
        required single link user -> User {
            readonly := True;
        }
    }
    type GroupChannel extending Channel {
        required multi link users -> User;
        property name -> bounded_str {
            constraint min_len_value(0);
        }
    }
};